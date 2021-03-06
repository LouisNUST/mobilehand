###############################################################################
### Demo neural network
### Input : Color image of hand, trained neural network
### Output: Predicted 3D hand model
###############################################################################

import cv2
import time
import torch
import random
import argparse
import numpy as np
import open3d as o3d
import torchvision.transforms.functional as TF

from PIL import Image
from torchvision import transforms
from utils_neural_network import HMR


##########################
### Load video capture ###
##########################
# cap = cv2.VideoCapture(0) # Load video from webcam (Default index is usually 0 or 1)
cap = cv2.VideoCapture('../data/video.mp4') # Load video from file

# Get device
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

############################
### Load trained network ###
############################
dataset = 'freihand' 
model = HMR(stb_dataset=False)
model.load_state_dict(torch.load('../model/hmr_model_'+dataset+'_auc.pth'))
model.to(device)
model.eval()

############################
### Open3D visualization ###
############################
vis = o3d.visualization.Visualizer()
vis.create_window(width=224, height=224)
# Create a reference frame (camera)
mesh_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=100)
# Draw mesh model
rvec = torch.zeros((1,3), dtype=torch.float32, device=device)
beta = torch.zeros((1,10), dtype=torch.float32, device=device)
ppca = torch.zeros((1,10), dtype=torch.float32, device=device)
pose = model.mano.convert_pca_to_pose(ppca) 
vertices, joints = model.mano.forward(beta, pose, rvec)
mesh = o3d.geometry.TriangleMesh()
mesh.vertices = o3d.utility.Vector3dVector(vertices[0,:,:].cpu().detach())
mesh.triangles = o3d.utility.Vector3iVector(model.mano.F)
mesh.compute_vertex_normals()
mesh.paint_uniform_color([0.75, 0.75, 0.75])
# Draw see through mesh
line_set = o3d.geometry.LineSet.create_from_triangle_mesh(mesh)
line_set.paint_uniform_color([0.75, 0.75, 0.75])

def create_line_set_bone_pcd_joint():
    joints = np.zeros((21,3))

    # Draw the 20 bones (lines) connecting 21 joints
    # The lines below is the kinematic tree that defines the connection between parent and child joints
    # Below lists the definition of the 21 joints following standard convention
    #  0:Wrist, 
    #  1:TMCP, 2:TPIP, 3:TDIP, 4:TTIP (Thumb)
    #  5:IMCP, 6:IPIP, 7:IDIP, 8:ITIP (Index)
    #  9:MMCP,10:MPIP,11:MDIP,12:MTIP (Middle)
    # 13:RMCP,14:RPIP,15:RDIP,16:RTIP (Ring)
    # 17:PMCP,18:PPIP,19:PDIP,20:PTIP (Little)
    lines = [[0,1],  [1,2],   [2,3],  [3,4],
             [0,5],  [5,6],   [6,7],  [7,8],
             [0,9], [9,10], [10,11],[11,12],
             [0,13],[13,14],[14,15],[15,16],
             [0,17],[17,18],[18,19],[19,20]]
    colors = [[255, 0, 0], [255, 60, 0], [255, 120, 0], [255, 180, 0], # Thumb red
              [0, 255, 0], [60, 255, 0], [120, 255, 0], [180, 255, 0], # Index green yellow
              [0, 255, 0], [0, 255, 60], [0, 255, 120], [0, 255, 180], # Middle green
              [0, 0, 255], [0, 60, 255], [0, 120, 255], [0, 180, 255], # Ring blue cyan
              [0, 0, 255], [60, 0, 255], [120, 0, 255], [180, 0, 255]] # Little blue magenta                 
    colors = np.array(colors) / 255

    line_set = o3d.geometry.LineSet()
    line_set.lines  = o3d.utility.Vector2iVector(lines)
    line_set.points = o3d.utility.Vector3dVector(joints)
    line_set.colors = o3d.utility.Vector3dVector(colors)

    # Draw the 21 joints (pcd)
    colors = [[0,0,0], # Black wrist
              [255, 0, 0], [255, 60, 0], [255, 120, 0], [255, 180, 0], # Thumb blue
              [0, 255, 0], [60, 255, 0], [120, 255, 0], [180, 255, 0], # Index green blue
              [0, 255, 0], [0, 255, 60], [0, 255, 120], [0, 255, 180], # Middle green red
              [0, 0, 255], [0, 60, 255], [0, 120, 255], [0, 180, 255], # Ring red green
              [0, 0, 255], [60, 0, 255], [120, 0, 255], [180, 0, 255]] # Little red blue
    colors = np.array(colors) / 255
    
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(joints)
    pcd.colors = o3d.utility.Vector3dVector(colors)

    return line_set, pcd 

# Draw skeleton
line_set_bone_, pcd_joint_ = create_line_set_bone_pcd_joint()

vis.add_geometry(mesh_frame)
vis.add_geometry(mesh)
vis.add_geometry(line_set)
vis.add_geometry(line_set_bone_)
vis.add_geometry(pcd_joint_)

# Set camera view
ctr = vis.get_view_control()
ctr.set_up([0,-1,0]) # Set up as -y axis
ctr.set_front([0,0,-1]) # Set to looking towards -z axis
ctr.set_lookat([0,0,0]) # Set to center of view
ctr.set_zoom(1.5)


def draw_mesh2D(verts, faces, scale, trans, img, color=(200,200,200)):
    # Project 3D vertices to 2D points
    # Add homo coor verts 
    # matrix = np.array([
    #     [607.92271,         0, 314.78337],
    #     [        0, 607.88192, 236.42484],
    #     [        0,         0,         1]])
    # verts = np.hstack((verts, np.ones((verts.shape[0], 1))))
    # # Add empty translation to intrinsic camera matrix
    # matrix = np.hstack((matrix, np.zeros((3,1))))
    # uv = np.matmul(matrix, verts.T).T # matrix (3,4), verts (n,4) -> uv (n, 4)
    # uv = uv[:,:3]
    # uv = uv[:, :2] / uv[:, -1:] # (n, 2)
    # uv = uv.astype(np.int32) # Convert to integer

    # Weak perspective projection
    uv = verts[:,:2]*scale + trans

    # Draw the lines connecting the 2D points
    for f in faces:
        u0, v0 = uv[f[0],:]
        u1, v1 = uv[f[1],:]
        u2, v2 = uv[f[2],:]
        # p0 = (u0,v0)
        # p1 = (u1,v1)
        # p2 = (u2,v2)
        # pp = np.array([p0,p1,p2])
        # cv2.drawContours(img, [pp], 0, (0,0,255), -1)
        cv2.line(img, (u0,v0), (u1, v1), color, 1)
        cv2.line(img, (u1,v1), (u2, v2), color, 1)
        cv2.line(img, (u2,v2), (u0, v0), color, 1)

    return img


def display_opencv(img, msk, keypt):
    # Define color for joint
    color = [[0,0,0], # Wrist
             [255,0,0],[255,60,0],[255,120,0],[255,180,0], # Thumb
             [0,255,0],[60,255,0],[120,255,0],[180,255,0], # Index
             [0,255,0],[0,255,60],[0,255,120],[0,255,180], # Middle
             [0,0,255],[0,60,255],[0,120,255],[0,180,255], # Ring
             [0,0,255],[60,0,255],[120,0,255],[180,0,255]] # Little

    # Define kinematic tree to link keypt together to form skeleton
    ktree = [0,          # Wrist
             0,1,2,3,    # Thumb
             0,5,6,7,    # Index
             0,9,10,11,  # Middle
             0,13,14,15, # Ring
             0,17,18,19] # Little             

    for i, (x, y) in enumerate(keypt):
        # Draw joint
        # cv2.circle(img, (x, y), 2, color[i], -1)
        cv2.circle(msk, (x, y), 2, color[i], -1)
        # Draw bone
        x0, y0 = keypt[ktree[i],:]
        # cv2.line(img, (x0, y0), (x, y), color[i], 1)
        cv2.line(msk, (x0, y0), (x, y), color[i], 1)

    combine = np.hstack((img, msk))

    return combine


def process_image(img):
    # Crop 480 x 480 (Assume video is 640 x 480)
    # img = img[:,80:560,:] # (480, 480, 3)

    # Resize to 224 x 224
    img = cv2.resize(img, (224, 224)) # (224, 224, 3)
    # Convert to RGB
    img_ = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) # (224, 224, 3)
    # Convert to torch tensor
    img_ = torch.as_tensor(img_, dtype=torch.float32)
    # Shift RGB channel infront and scale to [0,1]
    img_ = img_.permute(2,0,1)/255.0 # (3, 224, 224)

    return img_


while cap.isOpened():
    ret, image = cap.read()
    if not ret:
        break

    t0 = time.time()
    # Feedforward to model, get estimated results
    image = process_image(image)
    keypt_, joint_, vert_, angle_, param_ = model(image.to(device).unsqueeze(0), evaluation=True)
    t1 = time.time()

    # Convert image tensor to numpy for opencv to display
    image = (image.permute(1,2,0)*255).contiguous().numpy().astype(np.uint8)
    img = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    msk = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    # Update vertices of estimated mesh
    mesh.vertices = o3d.utility.Vector3dVector(vert_[0,:,:].cpu().detach())
    # Update points of estimated mesh
    line_set.points = o3d.utility.Vector3dVector(vert_[0,:,:].cpu().detach())
    # Update estimated joint
    line_set_bone_.points = o3d.utility.Vector3dVector(joint_[0,:,:].cpu().detach())
    pcd_joint_.points     = o3d.utility.Vector3dVector(joint_[0,:,:].cpu().detach())

    msk = draw_mesh2D(vert_[0,:,:].cpu().detach(), model.mano.F, 
        param_[:, 0].cpu().detach(), param_[:, 1:3].cpu().detach(), msk)

    combine_ = display_opencv(img.copy(), msk.copy(), keypt_[0].cpu().detach())

    vis.update_geometry(None)
    vis.poll_events()
    vis.update_renderer()

    # Add open3d screen capture
    img_o3d = (np.asarray(vis.capture_screen_float_buffer())*255).astype(np.uint8)
    img_o3d = img_o3d[...,::-1] # Convert opencv BGR to RGB
    combine_ = np.hstack((combine_, img_o3d))
    # Estimated
    cv2.imshow('estimated', combine_)

    # Note: Only measure inference time and ignore time taken to display images
    print('Inference time: %.3f ms, FPS: %.3f Hz' % ((t1-t0)*1000, 1.0/(t1-t0)))

    key = cv2.waitKey(1)
    if key==27: # Press 'esc' to quit
        break

cap.release()