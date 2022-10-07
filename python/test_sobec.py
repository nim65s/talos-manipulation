#####################
#  LOADING MODULES  #
#####################

import pinocchio as pin
import yaml

from sobec import RobotDesigner
from mpc_pointing import MPC_Point, MPCSettings_Point, OCPSettings_Point

from bullet_Talos import TalosDeburringSimulator
from plotter import TalosPlotter

################
#  PARAMETERS  #
################

enableGUI = False
T_total = 300

modelPath = "/opt/openrobots/share/example-robot-data/robots/talos_data/"
URDF = modelPath + "robots/talos_reduced.urdf"
SRDF = modelPath + "srdf/talos.srdf"

# Parameters filename
filename = "/local/users/cperrot/talos-manipulation/config/settings_sobec.yaml"

####################
#  INITIALIZATION  #
####################

# Loading extra parameters from file
with open(filename, "r") as paramFile:
    params = yaml.safe_load(paramFile)

controlledJoints = params["robot"]["controlledJoints"]
toolFramePos = params["robot"]["toolFramePos"]

MPCparams = MPCSettings_Point()
OCPparams = OCPSettings_Point()

print("Loading data from file: \n" + filename)
OCPparams.readFromYaml(filename)
MPCparams.readFromYaml(filename)

# Robot model
design_conf = dict(
    urdfPath=URDF,
    srdfPath=SRDF,
    leftFootName="right_sole_link",
    rightFootName="left_sole_link",
    robotDescription="",
    controlledJointsNames=controlledJoints,
)
pinWrapper = RobotDesigner()
pinWrapper.initialize(design_conf)

gripper_SE3_tool = pin.SE3.Identity()
gripper_SE3_tool.translation[0] = toolFramePos[0]
gripper_SE3_tool.translation[1] = toolFramePos[1]
gripper_SE3_tool.translation[2] = toolFramePos[2]
pinWrapper.addEndEffectorFrame(
    "deburring_tool", "gripper_left_fingertip_3_link", gripper_SE3_tool
)

# MPC
MPC = MPC_Point(MPCparams, OCPparams, pinWrapper)
MPC.initialize(pinWrapper.get_q0(), pinWrapper.get_v0(), pin.SE3.Identity())

print("Robot successfully loaded")

# Simulator
simulator = TalosDeburringSimulator(
    URDF=URDF,
    targetPos=MPCparams.targetPos,
    rmodelComplete=pinWrapper.get_rModelComplete(),
    controlledJointsIDs=pinWrapper.get_controlledJointsIDs(),
    enableGUI=enableGUI,
)

# Plotter
plotter = TalosPlotter(pinWrapper.get_rModel(), T_total)

###############
#  MAIN LOOP  #
###############
NcontrolKnots = 10
state = MPC.OCP.modelMaker.getState()
T = 0

while T < T_total:
    # Controller works faster than trajectory generation
    for i_control in range(NcontrolKnots):
        x_measured = simulator.getRobotState()

        # Compute torque to be applied by adding Riccati term
        torques = MPC.u0 + MPC.K0 @ state.diff(x_measured, MPC.x0)

        # Apply torque on complete model
        simulator.step(torques)

    MPC.iterate(x_measured, pin.SE3.Identity())
    plotter.logState(T, x_measured)
    plotter.logTorques(T, torques)
    plotter.logEndEffectorPos(
        T, MPC.designer.get_EndEff_frame().translation, MPCparams.targetPos
    )

    T += 1

simulator.end()
print("Simulation ended")
plotter.plotResults()
