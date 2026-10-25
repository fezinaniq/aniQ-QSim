import matplotlib.pyplot as plt
import numpy as np


def plot_bloch_sphere(qubit, title="Bloch Sphere"):
    alpha = qubit.state[0]
    beta = qubit.state[1]
    
    theta = 2 * np.arccos(np.abs(alpha))
    phi = np.angle(beta)
    
    if np.abs(beta) < 1e-9:
        phi = 0.0
    
   
    x = np.sin(theta) * np.cos(phi)
    y = np.sin(theta) * np.sin(phi)
    z = np.cos(theta)
    
    fig  = plt.figure(figsize=(8,8))
    ax = fig.add_subplot(111, projection='3d')
    ax.set_aspect("auto")
    
    u = np.linspace(0,2 * np.pi, 100)
    v = np.linspace(0,np.pi,100)
    sphere_x = np.outer(np.cos(u), np.sin(v))
    sphere_y = np.outer(np.sin(u), np.sin(v))
    sphere_z = np.outer(np.ones(np.size(u)), np.cos(v))
    ax.plot_surface(sphere_x, sphere_y, sphere_z, color='c', alpha=0.1)
    
    ax.plot([-1.1, 1.1], [0, 0], [0, 0], 'k--', lw=1) 
    ax.plot([0, 0], [-1.1, 1.1], [0, 0], 'k--', lw=1)
    ax.plot([0, 0], [0, 0], [-1.1, 1.1], 'k--', lw=1) 
    ax.text(1.2, 0, 0, 'x', fontsize=12)
    ax.text(0, 1.2, 0, 'y', fontsize=12)
    ax.text(0, 0, 1.2, 'z', fontsize=12)
    
    ax.text(0, 0, 1.1, r'$|0⟩$', fontsize=14, ha='center', va='center')
    ax.text(0, 0, -1.1, r'$|1⟩$', fontsize=14, ha='center', va='center')
    ax.text(1.1, 0, 0, r'$|+⟩$', fontsize=14, ha='center', va='center')
    ax.text(-1.1, 0, 0, r'$|-⟩$', fontsize=14, ha='center', va='center')
    ax.text(0, 1.1, 0, r'$|i⟩$', fontsize=14, ha='center', va='center')
    ax.text(0, -1.1, 0, r'$|-i⟩$', fontsize=14, ha='center', va='center')
    
    ax.plot([0, x], [0, y], [0, z], color='black', linewidth=8)
    
    ax.plot([0], [0], [0], marker='o', markersize=8, color='black', linestyle='None')
    ax.plot([x], [y], [z], marker='o', markersize=15, color='black', linestyle='None')
    
    
    ax.set_title(title, fontsize=16)
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.set_xlim([-1.2, 1.2])
    ax.set_ylim([-1.2, 1.2])
    ax.set_zlim([-1.2, 1.2])
    
    plt.show()    
