
import os
import random

from maro.simulator.scenarios import AbsBusinessEngine

from maro.event_buffer import MaroEvents, CascadeEvent, AtomEvent

from .units import UnitBase
from .world import World

from .config_parser import ConfigParser


class SupplyChainBusinessEngine(AbsBusinessEngine):
    def __init__(self, **kwargs):
        super().__init__(scenario_name="supply_chain", **kwargs)

        self._register_events()

        self._build_world()

        self._node_mapping = self.world.get_node_mapping()

        self._frame = self.world.frame

        self._action_steps = self.world.configs["action_steps"]

        # for update by unit
        self._unit_id_list = None

    @property
    def frame(self):
        return self._frame

    @property
    def snapshots(self):
        return self._frame.snapshots

    @property
    def configs(self):
        return self.world.configs

    def get_node_mapping(self) -> dict:
        return self._node_mapping

    def step(self, tick: int):
        self._step_by_facility(tick)

        if tick % self._action_steps == 0:
            decision_event = self._event_buffer.gen_decision_event(tick, None)

            self._event_buffer.insert_event(decision_event)

    def _step_by_facility(self, tick: int):
        for _, facility in self.world.facilities.items():
            facility.step(tick)

    def _step_by_units(self, tick: int):
        if self._unit_id_list is None:
            self._unit_id_list = [i for i in self.world.unit_id2index_mapping.keys()]

        random.shuffle(self._unit_id_list)

        for unit_id in self._unit_id_list:
            unit = self.world.get_entity(unit_id)

            unit.step(tick)

    def post_step(self, tick: int):
        # take snapshot
        if (tick + 1) % self._snapshot_resolution == 0:
            self._frame.take_snapshot(self.frame_index(tick))

        for facility in self.world.facilities.values():
            facility.post_step(tick)

        return tick+1 == self._max_tick

    def reset(self):
        self._frame.reset()
        self._frame.snapshots.reset()

        for _, facility in self.world.facilities.items():
            facility.reset()

    def _register_events(self):
        self._event_buffer.register_event_handler(MaroEvents.TAKE_ACTION, self._on_action_received)

    def _build_world(self):
        self.update_config_root_path(__file__)

        core_config = os.path.join(self._config_path, "..", "core.yml")
        config_path = os.path.join(self._config_path, "config.yml")

        parser = ConfigParser(core_config, config_path)

        self.world = World()

        self.world.build(parser.parse(), self.calc_max_snapshots())

    def _on_action_received(self, event):
        action = event.payload

        if action:
            # NOTE:
            # we assume that the action is a dictionary that
            # key is the id of unit
            # value is the action for specified unit, the type may different by different type

            for unit_id, control_action in action.items():
                # try to find the unit
                unit: UnitBase = self.world.get_entity(unit_id)

                # dispatch the action
                unit.set_action(control_action)
