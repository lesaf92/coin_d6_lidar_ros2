from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    share = FindPackageShare('m1ct_d2')
    return LaunchDescription([
        DeclareLaunchArgument('port', default_value='/dev/coin_d6'),
        DeclareLaunchArgument('frame_id', default_value='laser_link'),
        DeclareLaunchArgument('rviz', default_value='false'),
        Node(
            package='m1ct_d2',
            executable='m1ct_d2',
            output='screen',
            parameters=[
                PathJoinSubstitution([share, 'params', 'm1ct_d2.yaml']),
                {'port': LaunchConfiguration('port'),
                 'frame_id': LaunchConfiguration('frame_id')},
            ],
        ),
        # viewer only: gives RViz a TF tree; on a robot, URDF/robot_state_publisher owns this
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            arguments=['--frame-id', 'base_link', '--child-frame-id', LaunchConfiguration('frame_id')],
            condition=IfCondition(LaunchConfiguration('rviz')),
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            arguments=['-d', PathJoinSubstitution([share, 'rviz', 'coin_d6.rviz']),
                       '-f', 'base_link'],
            condition=IfCondition(LaunchConfiguration('rviz')),
        ),
    ])
