from bloch import *
from gates import *
from qubit import Qubit

q = Qubit()
print("initial qubit: ", q)
print("Probabilities:", q.measure_probabilities())
plot_bloch_sphere(q,title="before gate")

apply_gate(q,H)
print("After H: ", q.measure_probabilities())
plot_bloch_sphere(q,title="after gate")

q.measure()
print("collapsed state probabilities: ", q.measure_probabilities())
plot_bloch_sphere(q,title="collapse")




# Experiments:

# superpostion :
# apply_gate(q,H)

# Inteference (HZH):
# apply_gate(q,H)
# apply_gate(q,Z)
# apply_gate(q,H)

# double hadamard:
#apply_gate(q,X)
#apply_gate(q,X)


print(q, q.measure_probabilities())