import numpy as np

X = np.array([[0,1],
              [1,0]], dtype=complex)

H = (1/np.sqrt(2)) * np.array([[1,1],
                               [1,-1]],dtype=complex)

Z = np.array([[1, 0],
              [0, -1]], dtype=complex)

Y = np.array([[0, -1j],
              [1j, 0]], dtype=complex)

S = np.array([[1,0],
              [0, np.exp(1j * np.pi/2)]],dtype=complex)

T = np.array([[1,0],
              [0, np.exp(1j * np.pi/4)]],dtype=complex)

def apply_gate(qubit,gate):
   
    qubit.state = np.dot(gate,qubit.state)
    qubit.normalize()
    
    