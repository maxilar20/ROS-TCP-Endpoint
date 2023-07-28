#  Copyright 2020 Unity Technologies
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import rclpy
import socket
import re

from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSReliabilityPolicy
from rclpy.qos import QoSProfile

from .communication import RosReceiver

from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener
from geometry_msgs.msg import TransformStamped
from tf2_msgs.msg import TFMessage

import yaml


class RosSubscriber(RosReceiver):
    """
    Class to send messages outside of ROS network
    """

    def __init__(self, topic, message_class, tcp_server, queue_size=10):
        """

        Args:
            topic:         Topic name to publish messages to
            message_class: The message class in catkin workspace
            queue_size:    Max number of entries to maintain in an outgoing queue
        """
        strippedTopic = re.sub("[^A-Za-z0-9_]+", "", topic)
        self.node_name = f"{strippedTopic}_RosSubscriber"
        RosReceiver.__init__(self, self.node_name)
        self.topic = topic
        self.msg = message_class
        self.tcp_server = tcp_server
        self.queue_size = queue_size

        if self.topic == "/tf":
            print(self.msg)
            self.tf_buffer = Buffer()
            self.tf_listener = TransformListener(self.tf_buffer, self)
            self.timer = self.create_timer(5, self.send_tf)

        qos_profile = QoSProfile(depth=queue_size)

        # Start Subscriber listener function
        self.subscription = self.create_subscription(
            self.msg, self.topic, self.send, qos_profile  # queue_size
        )
        self.subscription

    def send(self, data):
        """
        Connect to TCP endpoint on client and pass along message
        Args:
            data: message data to send outside of ROS network

        Returns:
            self.msg: The deserialize message
        """

        if self.topic == "/tf":
            return self.msg

        self.tcp_server.send_unity_message(self.topic, data)
        return self.msg

    def send_tf(self):
        tf_msg = TFMessage()

        tf_dict = yaml.load(self.tf_buffer.all_frames_as_yaml())
        time_stamp = self.get_clock().now().to_msg()

        for child_frame, frame_data in tf_dict.items():
            t = TransformStamped()

            t.header.stamp = time_stamp
            t.header.frame_id = frame_data["parent"]
            t.child_frame_id = child_frame

            tf_stamped = self.get_tf(child_frame, frame_data["parent"])

            t.transform.translation = tf_stamped.transform.translation
            t.transform.rotation = tf_stamped.transform.rotation

            tf_msg.transforms.append(t)

        self.tcp_server.send_unity_message(self.topic, tf_msg)

    def get_tf(self, parent_frame, child_frame):
        try:
            return self.tf_buffer.lookup_transform(
                child_frame, parent_frame, rclpy.time.Time()
            )
        except:
            self.get_logger().info(
                f"Could not transform {child_frame} to {parent_frame}: {ex}"
            )
            return

    def unregister(self):
        """

        Returns:

        """
        self.destroy_subscription(self.subscription)
        self.destroy_node()
