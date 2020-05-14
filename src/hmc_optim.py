# %%
import json
import os
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
import tensorflow_probability as tfp

import mndo
from data import load_data, prepare_data
from objective import jacobian, jacobian_parallel, penalty

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# %%
# @tf.function
# @tf.function(experimental_compile=True)
def sample_chain(*args, **kwargs):
    """Since this is bulk of the computation, using @tf.function
    here to compile a static graph for tfp.mcmc.sample_chain significantly improves
    performance, especially when enabling XLA (Accelerated Linear Algebra).
    https://tensorflow.org/xla#explicit_compilation_with_tffunction
    https://github.com/tensorflow/probability/issues/728#issuecomment-573704750
    """
    return tfp.mcmc.sample_chain(*args, **kwargs)


# %%
mols_atoms, mols_coords, charges, titles, reference = load_data(query_size=100)
ref_energies = reference.iloc[:, 1].tolist()

with open("../parameters/parameters-pm3.json") as file:
    start_params = json.loads(file.read())

# %%
# param_keys needed for mndo.set_params
# param_values acts as initial condition for HMC kernel
param_keys, param_values = prepare_data(mols_atoms, start_params)
# param_values = [tf.Variable(x) for x in param_values]
param_values = [tf.random.truncated_normal([], stddev=0.5) for _ in param_keys]

tmp_molecule_file = "_tmp_molecules"
mndo_method = "PM3"
mndo.write_tmp_optimizer(
    mols_atoms, mols_coords, tmp_molecule_file, mndo_method,
)

mndo_input = mndo.get_inputs(
    mols_atoms,
    mols_coords,
    np.zeros_like(mols_atoms),
    range(len(mols_atoms)),
    mndo_method,
)

# %%
@tf.custom_gradient
def target_log_prob_fn(*param_vals):
    log_likelihood = -penalty(
        param_vals, param_keys, tmp_molecule_file, ref_props=ref_energies
    )

    def grad_fn(*dys):
        grad = jacobian_parallel(
            param_vals,
            mndo_input=mndo_input,
            param_keys=param_keys,
            dh=1e-5,
            # filename=tmp_molecule_file,
            ref_props=ref_energies,
        )
        return list(dys * grad)

    return log_likelihood, grad_fn


def real_target_log_prob_fn(*param_vals):
    res = tf.py_function(target_log_prob_fn, inp=param_vals, Tout=tf.float64)
    # Avoid tripping up sample_chain due to loss of output shape in tf.py_function
    # when used in a tf.function context. https://tinyurl.com/y9ttqdpt
    res.set_shape(param_vals[0].shape[:-1])  # assumes parameter is vector-valued
    return res


# %%
now = datetime.now().strftime("%Y.%m.%d-%H:%M:%S")
log_dir = f"runs/hmc-trace/{now}"
summary_writer = tf.summary.create_file_writer(log_dir, flush_millis=1000)


def trace_fn(cs, kr, summary_freq=10, callbacks=[]):
    """
    cs (current_state): (list of) tensor(s) constituting the position in parameter space
    kr (kernel_results): kernel diagnostics like energy, log likelihood, step size, etc.
    summary_freq: record stats every n steps (unused)
    callbacks: list of functions taking in current_state, output is added to trace
    """
    step = tf.cast(kr.step, tf.int64)
    nuts = kr.inner_results
    target_log_prob = nuts.target_log_prob

    with summary_writer.as_default():
        tf.summary.experimental.set_step(step)
        tf.summary.scalar("log likelihood (mse)", target_log_prob)
        tf.summary.scalar("energy", nuts.energy)
        tf.summary.scalar("log accept ratio", nuts.log_accept_ratio)
        tf.summary.scalar("leapfrogs taken", nuts.leapfrogs_taken)
        with tf.summary.record_if(tf.equal(step % summary_freq, 0)):
            tf.summary.histogram("step size", nuts.step_size)

        # tf.summary.scalar("step size", kr.new_step_size)
        # tf.summary.scalar("decay rate", kr.decay_rate)
        # tf.summary.scalar("error sum", kr.error_sum)

    if callbacks:
        return target_log_prob, [cb(*cs) for cb in callbacks]
    return target_log_prob


# %%
step_size = tf.cast(1e-3, tf.float64)
kernel = tfp.mcmc.NoUTurnSampler(real_target_log_prob_fn, step_size)
adaptive_kernel = tfp.mcmc.DualAveragingStepSizeAdaptation(
    kernel,
    num_adaptation_steps=100,
    # pkr: previous kernel results, ss: step size
    step_size_setter_fn=lambda pkr, new_ss: pkr._replace(step_size=new_ss),
    step_size_getter_fn=lambda pkr: pkr.step_size,
    log_accept_prob_getter_fn=lambda pkr: pkr.log_accept_ratio,
)

chain, trace, final_kernel_results = sample_chain(
    num_results=100,
    current_state=param_values,
    kernel=adaptive_kernel,
    return_final_kernel_results=True,
    trace_fn=trace_fn,
)

with open("../parameters/parameters-opt-hmc.json", "w") as f:
    json.dump([list(x) for x in chain], f)


# %%
fig, axs = plt.subplots(2, 2)
axs[0, 0].hist(chain)
axs[0, 0].set_title("chain histogram")
axs[0, 1].plot(chain)
axs[0, 1].set_title("chain plot")
axs[1, 0].hist(trace)
axs[1, 0].set_title("trace histogram")
axs[1, 1].plot(trace)
axs[1, 1].set_title("trace plot")