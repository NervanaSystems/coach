#
# Copyright (c) 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import numpy as np
from typing import List, Union, Tuple

from rl_coach.base_parameters import AgentParameters, VisualizationParameters, TaskParameters, PresetValidationParameters
from rl_coach.environments.environment import EnvironmentParameters, Environment
from rl_coach.level_manager import LevelManager
from rl_coach.utils import short_dynamic_import

from rl_coach.core_types import EnvironmentSteps
from rl_coach.graph_managers.graph_manager import GraphManager, ScheduleParameters


class HACGraphManager(GraphManager):
    """
    A simple HAC graph manager creates a deep hierarchy with a single agent per hierarchy level, and a single
    environment (on the bottom layer) which is interacted with.
    """
    def __init__(self, agents_params: List[AgentParameters], env_params: EnvironmentParameters,
                 schedule_params: ScheduleParameters, vis_params: VisualizationParameters,
                 consecutive_steps_to_run_non_top_levels: Union[EnvironmentSteps, List[EnvironmentSteps]],
                 preset_validation_params: PresetValidationParameters = PresetValidationParameters()):
        """
        :param agents_params: the parameters of all the agents in the hierarchy starting from the top level of the
                              hierarchy to the bottom level
        :param env_params: the parameters of the environment
        :param schedule_params: the parameters for scheduling the graph
        :param vis_params: the visualization parameters
        :param consecutive_steps_to_run_non_top_levels: the number of time steps that each level is ran.
            for example, when the top level gives the bottom level a goal, the bottom level can act for
            consecutive_steps_to_run_each_level steps and try to reach that goal. This is expected to be either
            an EnvironmentSteps which will be used for all levels, or an EnvironmentSteps for each level as a list.
        """
        super().__init__('hac_graph', schedule_params, vis_params)
        self.agents_params = agents_params
        self.env_params = env_params
        self.preset_validation_params = preset_validation_params
        self.should_test_current_sub_goal = None  # will be filled by the top level agent, and is used by all levels

        if isinstance(consecutive_steps_to_run_non_top_levels, list):
            if len(consecutive_steps_to_run_non_top_levels) != len(self.agents_params):
                raise ValueError("If the consecutive_steps_to_run_each_level is given as a list, it should match "
                                 "the number of levels in the hierarchy. Alternatively, it is possible to use a single "
                                 "value for all the levels, by passing an EnvironmentSteps")
        elif isinstance(consecutive_steps_to_run_non_top_levels, EnvironmentSteps):
            self.consecutive_steps_to_run_non_top_levels = consecutive_steps_to_run_non_top_levels

        for agent_params in agents_params:
            agent_params.visualization = self.visualization_parameters
            if agent_params.input_filter is None:
                agent_params.input_filter = self.env_params.default_input_filter()
            if agent_params.output_filter is None:
                agent_params.output_filter = self.env_params.default_output_filter()

        if len(self.agents_params) < 2:
            raise ValueError("The HAC graph manager must receive the agent parameters for at least two levels of the "
                             "hierarchy. Otherwise, use the basic RL graph manager.")

    def _create_graph(self, task_parameters: TaskParameters) -> Tuple[List[LevelManager], List[Environment]]:
        env = short_dynamic_import(self.env_params.path)(**self.env_params.__dict__,
                                                         visualization_parameters=self.visualization_parameters)

        for agent_params in self.agents_params:
            agent_params.task_parameters = task_parameters

        # we need to build the hierarchy in reverse order (from the bottom up) in order for the spaces of each level
        # to be known
        level_managers = []
        current_env = env
        # out_action_space = env.action_space
        for level_idx, agent_params in reversed(list(enumerate(self.agents_params))):
            agent_params.name = "agent_{}".format(level_idx)
            agent_params.is_a_highest_level_agent = level_idx == 0
            agent_params.is_a_lowest_level_agent = level_idx == len(self.agents_params) - 1

            agent = short_dynamic_import(agent_params.path)(agent_params)

            level_manager = LevelManager(
                agents=agent,
                environment=current_env,
                real_environment=env,
                steps_limit=EnvironmentSteps(1) if level_idx == 0
                            else self.consecutive_steps_to_run_non_top_levels,
                should_reset_agent_state_after_time_limit_passes=level_idx > 0,
                name="level_{}".format(level_idx)
            )
            current_env = level_manager
            level_managers.insert(0, level_manager)

        return level_managers, [env]



