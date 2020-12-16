# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import os

import numpy as np

from maro.rl import (
    Actor, AgentManagerMode, DistributedTrainingMode, Executor, LearnerActorComponent, KStepExperienceShaper
)
from maro.simulator import Env
from maro.utils import Logger, convert_dottable

from examples.cim.dqn.components.action_shaper import CIMActionShaper
from examples.cim.dqn.components.agent_manager import DQNAgentManager, create_dqn_agents
from examples.cim.dqn.components.config import set_input_dim
from examples.cim.dqn.components.experience_shaper import TruncatedExperienceShaper
from examples.cim.dqn.components.state_shaper import CIMStateShaper


def launch(config, distributed_config):
    set_input_dim(config)
    config = convert_dottable(config)
    distributed_config = convert_dottable(distributed_config)
    env = Env(config.env.scenario, config.env.topology, durations=config.env.durations)
    agent_id_list = [str(agent_id) for agent_id in env.agent_idx_list]
    state_shaper = CIMStateShaper(**config.env.state_shaping)
    action_shaper = CIMActionShaper(action_space=list(np.linspace(-1.0, 1.0, config.agents.algorithm.num_actions)))
    experience_shaper = TruncatedExperienceShaper(**config.env.experience_shaping)

    distributed_mode = os.environ.get("MODE", distributed_config.mode)
    if distributed_mode == "seed":
        executor = Executor(
            state_shaper, action_shaper, experience_shaper, DistributedTrainingMode.LEARNER_ACTOR,
            action_wait_timeout=distributed_config.action_wait_timeout
        )
    elif distributed_mode == "simple":
        executor = DQNAgentManager(
            name="distributed_cim_actor",
            mode=AgentManagerMode.INFERENCE,
            agent_dict=create_dqn_agents(agent_id_list, config.agents),
            state_shaper=state_shaper,
            action_shaper=action_shaper,
            experience_shaper=experience_shaper
        )
    else:
        raise ValueError(f'Supported distributed training modes: "simple", "seed", got {distributed_mode}')

    actor = Actor(
        env, executor,
        logger=Logger("cim_actor", auto_timestamp=False),
        group_name=os.environ.get("GROUP", distributed_config.group),
        expected_peers={LearnerActorComponent.LEARNER.value: 1},
        redis_address=(distributed_config.redis.hostname, distributed_config.redis.port),
        max_retries=15
    )
    actor.run()


if __name__ == "__main__":
    from examples.cim.dqn.components.config import config, distributed_config
    launch(config=config, distributed_config=distributed_config)