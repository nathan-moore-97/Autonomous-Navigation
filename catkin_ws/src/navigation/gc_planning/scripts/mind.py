#!/usr/bin/env python 
import gps_util
import rospy
from navigation_msgs.msg import WaypointsArray, LatLongPoint, VelAngle
from nav_msgs.msg import Path, Odometry
from sensor_msgs.msg import NavSatFix
from std_msgs.msg import Header, Float32
from geometry_msgs.msg import PointStamped, PoseStamped, Point
from visualization_msgs.msg import Marker
import tf.transformations as tf
import math
import cubic_spline_planner #might want to move where this is
import pure_pursuit #same as above
import matplotlib.pyplot as plt #THIS IS TEMPORARY
class mind(object):

    #Creates a poseStamped object from a point
    def create_poseStamped(self, point):
        stamped = PoseStamped()
        stamped.header = Header()
        stamped.header.frame_id = '/map'
        stamped.pose.position = point
        return stamped

    def create_marker(self, x, y, frame_id):
        marker = Marker()
        marker.header.frame_id = frame_id
        marker.header.stamp = rospy.Time.now()
        marker.ns = "my_namespace"
        marker.id = 0
        marker.type = 1 #cube
        marker.action = 0 #add
        marker.pose.position.x = x
        marker.pose.position.y = y
        marker.pose.position.z = 0

        #quat = tf.quaternion_from_euler(0,0,yaw)
        #marker.pose.orientation = quat

        marker.pose.orientation.x = 0.0
        marker.pose.orientation.y = 0.0
        marker.pose.orientation.z = 0.0
        marker.pose.orientation.w = 1.0
        marker.scale.x = 1.0
        marker.scale.y = 1.0
        marker.scale.z = 1.0
        marker.color.a = 1.0
        marker.color.r = 0.0
        marker.color.g = 1.0
        marker.color.b = 0.0

        return marker

    def __init__(self):
        rospy.init_node('mind')

        self.odom = Odometry()
        self.rp_dist = 99999999999
        self.stop_thresh = 5 #this is how many seconds something is away from us

        self.waypoints_s = rospy.Subscriber('/waypoints', WaypointsArray, self.waypoints_callback, queue_size=10) 
        self.odom_sub = rospy.Subscriber('/pose_and_speed', Odometry, self.odom_callback, queue_size=10) 
        self.rp_distance_sub = rospy.Subscriber('/rp_distance', Float32, self.rp_callback, queue_size=10) 
        self.points_pub = rospy.Publisher('/points', Path, queue_size=10, latch = True)
        self.path_pub = rospy.Publisher('/path', Path, queue_size=10, latch = True)
        self.motion_pub = rospy.Publisher('/nav_cmd', VelAngle, queue_size=10)
        self.target_pub = rospy.Publisher('/target_point', Marker, queue_size=10)
        self.target_twist_pub = rospy.Publisher('/target_twist', Marker, queue_size=10)

        rospy.spin()

    def odom_callback(self, msg):
        self.odom = msg

    def rp_callback(self, msg):
        if (msg.data <= 0.5):
            self.rp_dist = 99999999
        else:
            self.rp_dist = msg.data


    #This reads from the waypoints topic and TODO
    def waypoints_callback(self, msg):
        """
        Waypoints callback does way too much right now. All of the path stuff should be handled in a helper method
        """

        google_points = []

        #Reads each point in the waypoint topic into google_points
        for gps_point in msg.waypoints:
            point = gps_util.get_point(gps_point)
            google_points.append(point)

        print len(google_points)

        #Adds more points between the google points
        google_points_plus = gps_util.add_intermediate_points(google_points, 15.0)
        print len(google_points_plus)

        ax = []
        ay = []

        extra_points = Path()
        extra_points.header = Header()
        extra_points.header.frame_id = '/map'

        #Puts the x's and y's 
        for p in google_points_plus:
            extra_points.poses.append(self.create_poseStamped(p))
            ax.append(p.x)
            ay.append(p.y)

        self.points_pub.publish(extra_points)

        #calculate the spline
        cx, cy, cyaw, ck, s = cubic_spline_planner.calc_spline_course(ax, ay, ds=0.1)

        path = Path()
        path.header = Header()
        path.header.frame_id = '/map'

        for i in range(0, len(cx)):
            curve_point = Point()
            curve_point.x = cx[i]
            curve_point.y = cy[i]
            path.poses.append(self.create_poseStamped(curve_point))

        self.path_pub.publish(path)

        #================================================ pure persuit copy/pase ===============================================

        k = 0.1  # look forward gain
        Lfc = 3.5  # look-ahead distance
        Kp = 1.0  # speed propotional gain
        dt = 0.1  # [s]
        L = 2.9  # [m] wheel base of vehicle

        target_speed = 10.0 / 3.6  # [m/s]
        T = 100.0  # max simulation time

        # initial state
        pose = self.odom.pose.pose
        twist = self.odom.twist.twist

        quat = (pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w)
        angles = tf.euler_from_quaternion(quat)
        initial_v = math.sqrt(twist.linear.x ** 2 + twist.linear.y ** 2)
        state = State(x=pose.position.x, y=pose.position.y, yaw=angles[2], v=initial_v) #TODO this has to be where we start

        lastIndex = len(cx) - 1
        time = 0.0
        x = [state.x]
        y = [state.y]
        yaw = [state.yaw]
        v = [state.v]
        t = [0.0]
        target_ind = pure_pursuit.calc_target_index(state, cx, cy)

        while lastIndex > target_ind:
            ai = pure_pursuit.PIDControl(target_speed, state.v)
            di, target_ind = pure_pursuit.pure_pursuit_control(state, cx, cy, target_ind)

            #publish where we want to be
            mkr = self.create_marker(cx[target_ind], cy[target_ind], '/map')
            self.target_pub.publish(mkr)

            #publish an arrow with our twist
            arrow = self.create_marker(0, 0, '/base_link')
            arrow.type = 0 #arrow
            arrow.scale.x = 2.0
            arrow.scale.y = 1.0
            arrow.scale.z = 1.0
            arrow.color.r = 1.0
            arrow.color.g = 0.0
            arrow.color.b = 0.0
            #TODO di might be in radians so that might be causing the error
            quater = tf.quaternion_from_euler(0,0,di)
            arrow.pose.orientation.x = quater[0]
            arrow.pose.orientation.y = quater[1]
            arrow.pose.orientation.z = quater[2]
            arrow.pose.orientation.w = quater[3]
            self.target_twist_pub.publish(arrow)

            #go back to pure persuit
            state = self.update(state, ai, di)

            #time = time + dt

            x.append(state.x)
            y.append(state.y)
            yaw.append(state.yaw)
            v.append(state.v)
            t.append(time)

        # Test
        assert lastIndex >= target_ind, "Cannot goal"


        rospy.logerr("Done navigating")
        msg = VelAngle()
        msg.vel = 0
        msg.angle = 0
        msg.vel_curr = 0
        self.motion_pub.publish(msg)
        

    def update(self, state, a, delta):

        #this is looping until there is nothing infront of us
        r = rospy.Rate(1)
        pose = self.odom.pose.pose
        twist = self.odom.twist.twist

        current_spd = math.sqrt(twist.linear.x ** 2 + twist.linear.y ** 2)

        msg = VelAngle()
        msg.vel = a
        msg.angle = (delta*180)/math.pi
        msg.vel_curr = current_spd
        self.motion_pub.publish(msg)

        state.x = pose.position.x
        state.y = pose.position.y

        quat = (pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w)
        angles = tf.euler_from_quaternion(quat)

        state.yaw = angles[2]

        state.v = math.sqrt(twist.linear.x ** 2 + twist.linear.y ** 2)

        '''dt = 0.1
        L = 2.9
        state.x = state.x + state.v * math.cos(state.yaw) * dt
        state.y = state.y + state.v * math.sin(state.yaw) * dt
        state.yaw = state.yaw + state.v / L * math.tan(delta) * dt
        state.v = state.v + a * dt'''


        return state


class State:

    def __init__(self, x=0.0, y=0.0, yaw=0.0, v=0.0):
        self.x = x
        self.y = y
        self.yaw = yaw
        self.v = v


        #================================================ pure pursuit copy/pase END ===============================================


if __name__ == "__main__":
    try:
	mind()
    except rospy.ROSInterruptException:
	pass
