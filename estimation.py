# Copyright 2018, 2019, 2020 CNRS - Airbus SAS
# Author: Florent Lamiraux, Joseph Mirabel, Alexis Nicolin
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:

# 1. Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.

# 2. Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import sys

import argparse, numpy as np
from hpp import Quaternion, Transform
from hpp.corbaserver.manipulation import Constraints, ProblemSolver
from hpp.corbaserver.manipulation.robot import CorbaClient
from hpp.corbaserver import loadServerPlugin

from common_hpp import *

# parse arguments
p = argparse.ArgumentParser (description=
                             'Initialize estimation for the demo of Pyrene manipulating a box')
p.add_argument ('--ros-param', type=str, metavar='ros_param',
                help="The name of the ROS param containing the URDF.")
args = p.parse_args ()

loadServerPlugin ("estimation", "manipulation-corba.so")

footPlacement = True
projectRobotOnFloor = True
comConstraint = False
constantWaistYaw = True
fixedArmWhenGrasping = True

clients = CorbaClient(context="estimation")
if not clients.manipulation.problem.selectProblem("estimation"):
  clients.manipulation.problem.resetProblem()

robot, ps, vf, table, objects = makeRobotProblemAndViewerFactory(clients, rolling_table=True,
        rosParam=args.ros_param)

q_neutral = robot.getCurrentConfig()

ps.addPartialCom("talos", ["talos/root_joint"])
ps.addPartialCom("talos_box", ["talos/root_joint", "box/root_joint"])

# Static stability constraint
robot.createStaticStabilityConstraint(
    "balance/", "talos", robot.leftAnkle, robot.rightAnkle, init_conf
)
foot_placement = ["balance/pose-left-foot"]
foot_placement_complement = []

# Static stability constraint with box
robot.createStaticStabilityConstraint(
    "balance_box/", "talos_box", robot.leftAnkle, robot.rightAnkle, init_conf
)


# Gaze constraint
ps.createPositionConstraint(
    "gaze",
    "talos/rgbd_optical_joint",
    "box/root_joint",
    (0, 0, 0),
    (0, 0, 0),
    (True, True, False),
)

# Constraint of constant yaw of the waist
ps.createOrientationConstraint(
    "waist_yaw", "", "talos/root_joint", (0, 0, 0, 1), [True, True, True]
)
ps.setConstantRightHandSide("waist_yaw", False)

# Create lock joints for grippers
table_lock = list()

# lock position of table
table_lock.append(table.name + "/root_joint")

# Create locked joint for left arm
left_arm_lock = list()
for n in robot.jointNames:
    if n.startswith("talos/arm_left"):
        ps.createLockedJoint(n, n, [0])
        ps.setConstantRightHandSide(n, False)
        left_arm_lock.append(n)

# Create locked joint for right arm
right_arm_lock = list()
for n in robot.jointNames:
    if n.startswith("talos/arm_right"):
        ps.createLockedJoint(n, n, [0])
        ps.setConstantRightHandSide(n, False)
        right_arm_lock.append(n)

# Create locked joint for grippers
left_gripper_lock = list()
right_gripper_lock = list()
for n in robot.jointNames:
    s = robot.getJointConfigSize(n)
    r = robot.rankInConfiguration[n]
    if n.startswith("talos/gripper_right"):
        ps.createLockedJoint(n, n, init_conf[r : r + s])
        right_gripper_lock.append(n)
    elif n.startswith("talos/gripper_left"):
        ps.createLockedJoint(n, n, init_conf[r : r + s])
        left_gripper_lock.append(n)
    elif n in table_lock:
        ps.createLockedJoint(n, n, init_conf[r : r + s])
        ps.setConstantRightHandSide(n, False)

q_init = [
    0.5402763680625408,
    -0.833196863501999,
    1.0199316910041052,
    -0.03128842007165536,
    0.013789190720970665,
    0.7297271046306221,
    0.6828830395873728,
    -0.002517657851415276,
    0.03462520266527989,
    -0.5316498053579248,
    0.8402250533557625,
    -0.3730641123290547,
    -0.011780954381969872,
    -0.0025270209724267243,
    0.034480300571697056,
    -0.5168007496652326,
    0.8113706150231745,
    -0.3590584062316795,
    -0.011635750462120158,
    0.0,
    0.4392076095335054,
    0.2806705510519144,
    0.5,
    0.0019674899062759165,
    -0.5194264855927397,
    1.2349417194832937e-05,
    0.0007850050683513623,
    0.10090925286890041,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    -0.2814831804277627,
    -0.5,
    -0.004238959829568303,
    -0.5200522586579716,
    0.00014996678886283413,
    -0.0015425422291322729,
    0.10092910629223316,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.5143008291852817,
    0.0455661913503581,
    0.45891797741593393,
    -0.25,
    0.832,
    -0.5,
    0.5,
    0.5,
    0.5,
    0,
    0,
    0,
    0,
    0,
    0,
    1,
]


# Set robot to neutral configuration before building constraint graph
robot.setCurrentConfig(q_neutral)
graph = makeGraph(robot, table, objects)

# Add other locked joints in the edges.
for edgename, edgeid in graph.edges.iteritems():
    graph.addConstraints(
        edge=edgename, constraints=Constraints(lockedJoints=table_lock)
    )
# Add gaze and and COM constraints to each node of the graph
if comConstraint:
    for nodename, nodeid in graph.nodes.iteritems():
        graph.addConstraints(
            node=nodename, constraints=Constraints(numConstraints=["com_talos", "gaze"])
        )

# Add locked joints and foot placement constraints in the graph,
# add foot placement complement in each edge.
if footPlacement:
    for edgename, edgeid in graph.edges.iteritems():
        graph.addConstraints(
            edge=edgename,
            constraints=Constraints(numConstraints=foot_placement_complement),
        )

if constantWaistYaw:
    for edgename, edgeid in graph.edges.iteritems():
        graph.addConstraints(
            edge=edgename, constraints=Constraints(numConstraints=["waist_yaw"])
        )

graph.addConstraints(
    graph=True,
    constraints=Constraints(
        numConstraints=foot_placement,
        lockedJoints=left_gripper_lock + right_gripper_lock,
    ),
)

# On the real robot, the initial configuration as measured by sensors is very
# likely not in any state of the graph. State "starting_state" and transition
# "starting_motion" are aimed at coping with this issue.
graph.createNode("starting_state")
graph.createEdge("starting_state", "free", "starting_motion", isInNode="starting_state")
graph.addConstraints(
    node="starting_state", constraints=Constraints(numConstraints=["place_box"])
)
graph.addConstraints(
    edge="starting_motion",
    constraints=Constraints(
        numConstraints=["place_box/complement"], lockedJoints=table_lock
    ),
)

# Transitions from state 'free'
e_l1 = "talos/left_gripper > box/handle1 | f"
e_r1 = "talos/right_gripper > box/handle1 | f"
e_l2 = "talos/left_gripper > box/handle2 | f"
e_r2 = "talos/right_gripper > box/handle2 | f"
e_l3 = "talos/left_gripper > box/handle3 | f"
e_r3 = "talos/right_gripper > box/handle3 | f"
e_l4 = "talos/left_gripper > box/handle4 | f"
e_r4 = "talos/right_gripper > box/handle4 | f"
# Transitions from one grasp to two grasps
e_l1_r2 = "talos/right_gripper > box/handle2 | 0-0"
e_l1_r4 = "talos/right_gripper > box/handle4 | 0-0"
e_r1_l2 = "talos/left_gripper > box/handle2 | 1-0"
e_r1_l4 = "talos/left_gripper > box/handle4 | 1-0"
e_l2_r1 = "talos/right_gripper > box/handle1 | 0-3"
e_l2_r3 = "talos/right_gripper > box/handle3 | 0-3"
e_r2_l1 = "talos/left_gripper > box/handle3 | 1-3"
e_r2_l3 = "talos/left_gripper > box/handle3 | 1-3"
e_r3_l4 = "talos/left_gripper > box/handle4 | 1-2"
e_r3_l2 = "talos/left_gripper > box/handle2 | 1-2"
e_l3_r4 = "talos/right_gripper > box/handle4 | 0-2"
e_l3_r2 = "talos/right_gripper > box/handle2 | 0-2"
e_l4_r1 = "talos/right_gripper > box/handle1 | 0-3"
e_l4_r3 = "talos/right_gripper > box/handle3 | 0-3"
e_r4_l1 = "talos/left_gripper > box/handle1 | 1-3"
e_r4_l3 = "talos/left_gripper > box/handle3 | 1-3"
# Transition from 'free' to first waypoint
e_l1_app = e_l1 + "_01"
e_r3_app = e_r3 + "_01"
e_l4_app = e_l4 + "_01"
e_r2_app = e_r2 + "_01"

if fixedArmWhenGrasping:
    leftArmConstraint = Constraints(lockedJoints=left_arm_lock)
    rightArmConstraint = Constraints(lockedJoints=right_arm_lock)

    graph.addConstraints(edge=e_l1_app, constraints=rightArmConstraint)
    graph.addConstraints(edge=e_r3_app, constraints=leftArmConstraint)
    graph.addConstraints(edge=e_l4_app, constraints=rightArmConstraint)
    graph.addConstraints(edge=e_r2_app, constraints=leftArmConstraint)
    graph.initialize()


ps.setRandomSeed(123)
ps.selectPathProjector("Progressive", 0.2)
ps.selectPathValidation("Discretized", 0.01)
graph.initialize()

# Set Gaussian configuration shooter.
robot.setCurrentConfig(q_init)
# Set variance to 0.1 for all degrees of freedom
sigma = robot.getNumberDof() * [0.1]
# Set variance to 0.05 for robot free floating base
rank = robot.rankInVelocity[robot.displayName + "/root_joint"]
sigma[rank : rank + 6] = 6 * [0.0]
# Set variance to 0.05 for box
rank = robot.rankInVelocity[objects[0].name + "/root_joint"]
sigma[rank : rank + 6] = 6 * [0.05]
# Set variance to 0.05 for table
rank = robot.rankInVelocity[table.name + "/root_joint"]
sigma[rank : rank + 6] = 6 * [0.05]
robot.setCurrentVelocity(sigma)
ps.setParameter("ConfigurationShooter/Gaussian/useRobotVelocity", True)
ps.client.basic.problem.selectConfigurationShooter("Gaussian")
# Set Optimization parameters
ps.setParameter("SimpleTimeParameterization/safety", 0.5)
ps.setParameter("SimpleTimeParameterization/order", 2)
ps.setParameter("SimpleTimeParameterization/maxAcceleration", 2.0)

q_tag11_down = q_init[:]
q_tag11_up = q_init[:]

rankO = robot.rankInConfiguration["box/root_joint"]
qT = Quaternion(q_tag11_up[rankO + 3 : rankO + 7])
q_tag11_up[rankO + 3 : rankO + 7] = (qT * Quaternion([0, 0, 1, 0])).toTuple()

sys.exit(0)

# q_init = robot.shootRandomConfig ()
# Define problem
res, q_init, err = graph.applyNodeConstraints("free", q_init)
if not res:
    raise RuntimeError("Failed to project initial configuration")

q_goal = q_init[::]
q_goal[-4:] = [-0.5, -0.5, -0.5, 0.5]

solver = Solver(ps, graph, q_init, q_goal, e1, e2, e3, e4, e14, e23)
