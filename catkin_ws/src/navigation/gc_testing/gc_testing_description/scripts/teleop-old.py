#!/usr/bin/env python 

import rospy
import readchar
import time
import math
from navigation_msgs.msg import vel_angle
from nav_msgs.msg import Odometry

class teleop(object):
    def __init__(self):
        rospy.init_node('teleop')

        self.motion_pub = rospy.Publisher('/nav_cmd', vel_angle, queue_size=10)
        self.vel_sub = rospy.Subscriber('/pose_and_speed', Odometry, self.vel_callback, queue_size = 10)

        print 'Move with WSAD\nCTRL-C to exit\n'
        rate = rospy.Rate(10)

        self.prev_key = 1
        self.cur_vel = 0.0

        while (True):
            key = readchar.readkey()

            if (ord(key) == 3):
                exit(0)

            msg = vel_angle()
            #msg.vel_curr = 0 #ord(key)
            msg.vel = 0.0
            msg.angle = 0.0

            #W pressed
            if (ord(key) == 119):
                msg.vel_curr = self.key_check(ord(key), 4.0)
                msg.vel = 4.0
            #A pressed
            elif (ord(key) == 97):
                msg.vel = 1.0
                msg.vel_curr = self.key_check(ord(key), 1.0)
                msg.angle = -360
            #S pressed
            elif (ord(key) == 115):
                msg.vel_curr = self.key_check(ord(key), 0.01)
                msg.vel = 0.01
            #D pressed
            elif (ord(key) == 100):
                msg.vel = 1.0
                msg.vel_curr = self.key_check(ord(key), 1.0)
                msg.angle = 360


            self.motion_pub.publish(msg)
            #rate.sleep()

            #time.sleep(0.05)

        #rospy.spin()

    def key_check(self, key, target):
        #print key, self.prev_key
        if key != self.prev_key:
            self.prev_key = key
            return self.cur_vel

        if self.cur_vel < target - 0.05:
            self.cur_vel = self.cur_vel + 0.05
            return self.cur_vel

        if self.cur_vel > target + 0.05:
            self.cur_vel = self.cur_vel - 0.05
            return self.cur_vel

        self.cur_vel = target
        return self.cur_vel

    def vel_callback(self, msg):
        x_spd = msg.twist.twist.linear.x
        y_spd = msg.twist.twist.linear.y
        self.cur_vel = math.sqrt(x_spd ** 2 + y_spd ** 2)


if __name__ == "__main__":
    try:
	teleop()
    except rospy.ROSInterruptException:
	pass

