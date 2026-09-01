import time
import json

from as64core.resource_utils import resource_path

processes = {}


def register_process(name, process):
    processes[name] = process


def insert_global_hook(name, process):
    processes[name] = process


class ProcessorDefinitionError(Exception):
    """
    Raised when a .processor file references a process, signal, or
    transition target that doesn't exist, or is otherwise malformed.
    Always includes the offending file path and the specific item at fault.
    """


class ProcessorGenerator(object):
    INITIAL_PROCESS = "initial_process"
    INHERIT = "inherit"
    OVERRIDE = "override"
    TRANSITIONS = "transitions"
    SUB_PROCESSORS = "sub_processors"

    @staticmethod
    def generate(file_path):
        # Load processor file
        file = ProcessorGenerator._open_file(file_path)
        if not file:
            raise ProcessorDefinitionError(f"{file_path}: file not found or unreadable")

        try:
            sub_processor_paths = file[ProcessorGenerator.SUB_PROCESSORS]
            initial_process_key = file[ProcessorGenerator.INITIAL_PROCESS]
            inherit_path = file[ProcessorGenerator.INHERIT]
            local_transitions = file[ProcessorGenerator.TRANSITIONS]
        except KeyError as e:
            raise ProcessorDefinitionError(f"{file_path}: missing required field {e}")

        sub_processors = {}
        for sub_processor_key, sub_processor_path in sub_processor_paths.items():
            sub_processors[sub_processor_key] = ProcessorGenerator.generate(sub_processor_path)

        # Create blank processor instance
        processor = Processor()

        # Set initial process
        try:
            processor.initial_process = processes[initial_process_key]
        except KeyError:
            try:
                processor.initial_process = sub_processors[initial_process_key]
            except KeyError:
                raise ProcessorDefinitionError(
                    f"{file_path}: initial_process '{initial_process_key}' is not a registered process or sub-processor"
                )

        # Copy all transitions from inherited processor (single inheritance only)
        transitions = {}
        if inherit_path:
            inherit_file = ProcessorGenerator._open_file(inherit_path)
            if not inherit_file:
                raise ProcessorDefinitionError(f"{file_path}: inherit target '{inherit_path}' not found or unreadable")
            try:
                transitions = inherit_file[ProcessorGenerator.TRANSITIONS]
            except KeyError as e:
                raise ProcessorDefinitionError(f"{inherit_path}: missing required field {e}")

        # Set/override with all local transitions
        for transition in local_transitions:
            transitions[transition] = local_transitions[transition]

        # Add transitions to processor
        for process_key in transitions:
            for signal in transitions[process_key]:
                signal_location = signal.split(".")[0]
                signal_value = signal.split(".")[1]

                # Define Transition
                try:
                    t_process = processes[process_key]
                except KeyError:
                    try:
                        t_process = sub_processors[process_key]
                    except KeyError:
                        raise ProcessorDefinitionError(
                            f"{file_path}: transition source '{process_key}' is not a registered process or sub-processor"
                        )

                try:
                    t_signal = processes[signal_location].signals[signal_value]
                except KeyError:
                    try:
                        t_signal = sub_processors[signal_location].signals[signal_value]
                    except KeyError:
                        raise ProcessorDefinitionError(
                            f"{file_path}: transition signal '{signal}' on process '{process_key}' is not a known signal"
                        )

                next_key = transitions[process_key][signal]
                try:
                    t_next = processes[next_key]
                except KeyError:
                    try:
                        t_next = sub_processors[next_key]
                    except KeyError:
                        raise ProcessorDefinitionError(
                            f"{file_path}: transition target '{next_key}' (process '{process_key}', signal '{signal}') "
                            f"is not a registered process or sub-processor"
                        )

                processor.add_transition(Transition(t_process, t_signal, t_next))

        return processor

    @staticmethod
    def _open_file(file_path):
        try:
            with open(resource_path(file_path)) as file:
                data = json.load(file)
        except FileNotFoundError:
            return None
        except PermissionError:
            return None

        return data


class Signal(object):
    """
    Object used to define transition relationships between processes
    """
    def __init__(self, name=""):
        self._name = name

    def name(self):
        return self._name


class Transition(object):
    """
    Define state transition behaviour between two processes given a Signal object
    """
    def __init__(self, process, signal, next_process):
        self.process = process
        self.signal = signal
        self.next_process = next_process

    def valid(self, process, signal):
        return self.process == process and self.signal == signal


class Process(object):
    LOOP = Signal()

    def __init__(self):
        self.signals = {"LOOP": Signal()}
        self._transition_time = time.time()

    def execute(self):
        return self.signals["LOOP"]

    def on_transition(self):
        self._transition_time = time.time()

    def relinquish(self):
        return True

    def loop_time(self):
        return time.time() - self._transition_time

    def register_signal(self, name):
        self.signals[name] = Signal()


class Processor(Process):
    def __init__(self):
        super().__init__()

        # Processor
        self._initial_process = None
        self._prev_process = None
        self._current_process = None
        self._transitions = []

    @property
    def initial_process(self):
        return self._initial_process

    @initial_process.setter
    def initial_process(self, process):
        self._initial_process = process
        self._current_process = process

    def execute(self):
        if not self._current_process:
            return

        # If transitioning from a different process, call on_transition
        if self._current_process != self._prev_process:
            self._current_process.on_transition()
            print("Transition:", type(self._current_process).__name__)

        # Execute current process
        result = self._current_process.execute()

        next_process = None

        # Process LOOP signals, setting the next process to be the current process, otherwise check for transitions
        if result == self._current_process.signals["LOOP"]:
            next_process = self._current_process
        else:
            for transition in self._transitions:
                if transition.valid(self._current_process, result):
                    next_process = transition.next_process
                    break

        # Set processes for next execution
        self._prev_process = self._current_process
        self._current_process = next_process

        # If no valid transition is found, return result up processor chain
        if not next_process:
            return result
        else:
            return self.signals["LOOP"]

    def on_transition(self):
        """ On transition ensure processor is started from its initial process. """
        self._prev_process = None
        self._current_process = self._initial_process

    def add_transition(self, t):
        self._transitions.append(t)

    def relinquish(self):
        try:
            return self._current_process.relinquish()
        except AttributeError:
            return True


class ProcessorSwitch(object):
    def __init__(self):
        self._processors = {}
        self._current_processor = ""
        self._prev_processor = ""

    def execute(self, process_name):
        try:
            if process_name != self._current_processor:
                if self._processors[self._current_processor].relinquish():
                    self._current_processor = process_name

            if process_name != self._prev_processor:
                self._processors[process_name].on_transition()

            self._processors[self._current_processor].execute()

            self._prev_processor = process_name
        except (KeyError, AttributeError):
            pass

    def register_processor(self, name, processor):
        self._processors[name] = processor
