import elastica as ea

import numpy as np
from elastica.timestepper.symplectic_steppers import PositionVerlet
from elastica.timestepper import integrate
from elastica.external_forces import UniformTorques
from tumbling_unconstrained_rod_postprocessing import (
    EndpointforcesWithTimeFactor,
    EndpointtorqueWithTimeFactor,
    plot_video_with_surface,
    adjust_square_cross_section,
    lamda_t_function,
)
from matplotlib import pyplot as plt
import json

n_elem = 256
start = np.array([0.0, 0.0, 8.0])
end = np.array([6.0, 0.0, 0.0])
direction = np.array([0.6, 0.0, -0.8])
normal = np.array([0.0, 1.0, 0.0])
base_length = 10

side_length = 0.01


base_radius = side_length / (np.pi ** (1 / 2))


density = 1e4
youngs_modulus = 1e7
poisson_ratio = 0
shear_modulus = youngs_modulus / (poisson_ratio + 1.0)


class NonConstrainRodSimulator(
    ea.BaseSystemCollection, ea.Constraints, ea.Forcing, ea.Damping, ea.CallBacks
):
    pass


square_rod_sim = NonConstrainRodSimulator()

square_rod = ea.CosseratRod.straight_rod(
    n_elem,
    start,
    direction,
    normal,
    base_length,
    base_radius,
    density,
    youngs_modulus=youngs_modulus,
)


adjust_square_cross_section(square_rod, youngs_modulus, side_length)


print("mass_second_moment_of_inertia=", square_rod.mass_second_moment_of_inertia)
print("bend_matrix=", square_rod.bend_matrix)

square_rod_sim.append(square_rod)

dl = base_length / n_elem
dt = 0.01 * dl / 1

origin_force = np.array([0.0, 0.0, 0.0])
end_force = np.array([20.0, 0.0, 0.0])

square_rod_sim.add_forcing_to(square_rod).using(
    EndpointforcesWithTimeFactor, origin_force, end_force, lamda_t_function
)


square_rod_sim.add_forcing_to(square_rod).using(
    EndpointtorqueWithTimeFactor,
    1,
    lamda_t_function,
    direction=np.array([0.0, 200.0, -100.0]),
)

square_rod_sim.dampen(square_rod).using(
    ea.AnalyticalLinearDamper,
    damping_constant=0.0,
    time_step=dt,
)

print("Forces added to the rod")

final_time = 20
total_steps = int(final_time / dt)

print("Total steps to take", total_steps)

rendering_fps = 30
step_skip = int(1.0 / (rendering_fps * dt))


class TumblingUnconstrainedRodCallBack(ea.CallBackBaseClass):
    def __init__(self, step_skip: int, callback_params: dict):
        ea.CallBackBaseClass.__init__(self)
        self.every = step_skip
        self.callback_params = callback_params

    def make_callback(self, system, time, current_step: int):
        if current_step % self.every == 0:
            self.callback_params["time"].append(time)
            self.callback_params["step"].append(current_step)
            self.callback_params["position"].append(system.position_collection.copy())
            self.callback_params["radius"].append(system.radius.copy())
            self.callback_params["velocity"].append(system.velocity_collection.copy())
            self.callback_params["avg_velocity"].append(
                system.compute_velocity_center_of_mass()
            )
            self.callback_params["center_of_mass"].append(
                system.compute_position_center_of_mass()
            )


if __name__ == "__main__":

    recorded_history = ea.defaultdict(list)
    square_rod_sim.collect_diagnostics(square_rod).using(
        TumblingUnconstrainedRodCallBack,
        step_skip=step_skip,
        callback_params=recorded_history,
    )

    square_rod_sim.finalize()
    print("System finalized")

    timestepper = PositionVerlet()
    integrate(timestepper, square_rod_sim, final_time, total_steps)

    with open("TumblingUnconstrainedRod.json", "r") as file:
        analytic_data = json.load(file)

    time_analytic = analytic_data["time_analytic"]
    mass_center_analytic = analytic_data["mass_center_analytic"]

    plt.plot(
        time_analytic,
        mass_center_analytic[0],
        marker="*",
        color="black",
        label="x_analytic",
    )
    plt.plot(
        time_analytic,
        mass_center_analytic[1],
        marker="*",
        color="black",
        label="y_analytic",
    )
    plt.plot(
        time_analytic,
        mass_center_analytic[2],
        marker="*",
        color="black",
        label="z_analytic",
    )

    mass_center = np.array(recorded_history["center_of_mass"])

    plt.plot(recorded_history["time"][0:240], mass_center[:, 0][0:240], label="x")
    plt.plot(recorded_history["time"][0:240], mass_center[:, 1][0:240], label="y")
    plt.plot(recorded_history["time"][0:240], mass_center[:, 2][0:240], label="z")

    plt.xlabel("Time/(second)")  # X-axis label
    plt.ylabel("Center of mass")  # Y-axis label
    plt.grid()
    plt.legend()  # Optional: Add a grid
    plt.show()

    plot_video_with_surface(
        [recorded_history],
        video_name="Tumbling_Unconstrained_Rod.mp4",
        fps=rendering_fps,
        step=1,
        # The following parameters are optional
        x_limits=(0, 200),  # Set bounds on x-axis
        y_limits=(-4, 4),  # Set bounds on y-axis
        z_limits=(0.0, 8),  # Set bounds on z-axis
        dpi=100,  # Set the quality of the image
        vis3D=True,  # Turn on 3D visualization
        vis2D=False,  # Turn on projected (2D) visualization
    )
