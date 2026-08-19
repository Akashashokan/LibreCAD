from pydexpi.dexpi_classes import instrumentation


def add_signal_generating_function_to_instrumentation_function(
    instrumentation_function: instrumentation.ProcessInstrumentationFunction,
    signal_generating_function: instrumentation.ProcessSignalGeneratingFunction,
    measuring_line: instrumentation.MeasuringLineFunction,
) -> None:
    """
    Add a signal generating function to a process instrumentation function via a measuring line.

    Parameters
    ----------
    instrumentation_function : instrumentation.ProcessInstrumentationFunction
        The process instrumentation function that the generation function should be added to.
    signal_generating_function : instrumentation.ProcessSignalGeneratingFunction
        The function that generates the signal.
    measuring_line : instrumentation.MeasuringLineFunction
        The line that conveys the signal from the generating function to the instrumentation function.

    Raises
    ------
    ValueError
        If the measuring line already exists in the instrumentation function.
        If the signal generating function already exists in the instrumentation function.
        If the measuring line already has a source that is not the signal generating function.
        If the measuring line already has a target that is not the instrumentation function.
    """

    # Some consistency checks
    if measuring_line in instrumentation_function.signalConveyingFunctions:
        raise ValueError("The measuring line already exists in the instrumentation function.")
    if signal_generating_function in instrumentation_function.processSignalGeneratingFunctions:
        raise ValueError(
            "The signal generating function already exists in the instrumentation function."
        )
    if (
        measuring_line.source is not signal_generating_function
        and measuring_line.source is not None
    ):
        raise ValueError("The measuring line already has a source.")
    if measuring_line.target is not instrumentation_function and measuring_line.target is not None:
        raise ValueError("The measuring line already has a target.")

    # Connect measuring line
    measuring_line.source = signal_generating_function
    measuring_line.target = instrumentation_function

    # Add line and generating function to instrumentation function
    instrumentation_function.signalConveyingFunctions.append(measuring_line)
    instrumentation_function.processSignalGeneratingFunctions.append(signal_generating_function)


def add_signal_opc_to_instrumentation_function(
    instrumentation_function: instrumentation.ProcessInstrumentationFunction,
    signal_opc: instrumentation.SignalOffPageConnector,
    signal_line: instrumentation.SignalLineFunction,
) -> None:
    """
    Add a signal off-page connector to an instrumentation function via a signal line.

    The direction of the signal line is determined by the type of the signal OPC.
    If the signal OPC is a FlowOutSignalOffPageConnector, the signal line is outgoing.

    Parameters
    ----------
    instrumentation_function : instrumentation.ProcessInstrumentationFunction
        The instrumentation function to which the off-page connector is added to.
    signal_opc : instrumentation.SignalOffPageConnector
        The signal off-page connector to add.
    signal_line : instrumentation.SignalLineFunction
        The signal line that connects the instrumentation function and the off-page connector.

    Raises
    ------
    ValueError
        If the signal OPC already exists in the instrumentation function.
        If the signal line already exists in the instrumentation function.
        If the signal line already has a target (for outgoing signals).
        If the signal line already has a source (for incoming signals).
    """

    # Some consistency checks
    if signal_opc in instrumentation_function.signalConnectors:
        raise ValueError("The signal OPC already exists in the instrumentation function.")
    if signal_line in instrumentation_function.signalConveyingFunctions:
        raise ValueError("The signal line already exists in the instrumentation function.")

    is_outgoing = isinstance(signal_opc, instrumentation.FlowOutSignalOffPageConnector)
    is_incoming = isinstance(signal_opc, instrumentation.FlowInSignalOffPageConnector)
    if not is_outgoing and not is_incoming:
        raise ValueError("The signal_opc is not a valid OPC.")

    if is_outgoing:
        # Some consistency checks
        if signal_line.target is not signal_opc and signal_line.target is not None:
            raise ValueError("The signal line already has a target.")
        if signal_line.source is not instrumentation_function and signal_line.source is not None:
            raise ValueError("The signal line already has a source.")

        # Connect signal line
        signal_line.target = signal_opc
        signal_line.source = instrumentation_function

        # Add line and generating function to instrumentation function
        instrumentation_function.signalConveyingFunctions.append(signal_line)
        instrumentation_function.signalConnectors.append(signal_opc)

    else:
        if signal_line.source is not signal_opc and signal_line.source is not None:
            raise ValueError("The signal line already has a source.")
        if signal_line.target is not instrumentation_function and signal_line.target is not None:
            raise ValueError("The signal line already has a target.")

        # Connect signal line
        signal_line.source = signal_opc
        signal_line.target = instrumentation_function

        # Add line and generating function to instrumentation function
        instrumentation_function.signalConveyingFunctions.append(signal_line)
        instrumentation_function.signalConnectors.append(signal_opc)


def add_actuating_function_to_instrumentation_function(
    instrumentation_function: instrumentation.ProcessInstrumentationFunction,
    actuating_function: instrumentation.ActuatingFunction
    | instrumentation.ActuatingElectricalFunction,
    signal_line: instrumentation.SignalLineFunction,
):
    """
    Add an actuating function to an instrumentation function via a signal line.

    The actuating function can be either a regular actuating function or an electrical actuating
    function.

    Parameters
    ----------
    instrumentation_function : instrumentation.ProcessInstrumentationFunction
        The instrumentation function the actuating function is added to.
    actuating_function : instrumentation.ActuatingFunction or instrumentation.ActuatingElectricalFunction
        The actuating function that will receive the signal.
    signal_line : instrumentation.SignalLineFunction
        The signal line that conveys the signal from the instrumentation function to the actuating function.

    Raises
    ------
    ValueError
        If the signal line already exists in the instrumentation function.
        If the actuating function already exists in the instrumentation function.
        If the signal line already has a source that is not the instrumentation function.
        If the signal line already has a target that is not the actuating function.
    """
    is_electrical = isinstance(actuating_function, instrumentation.ActuatingElectricalFunction)

    # Some consistency checks
    if signal_line in instrumentation_function.signalConveyingFunctions:
        raise ValueError("The signal line already exists in the instrumentation function.")
    if is_electrical:
        if actuating_function in instrumentation_function.actuatingElectricalFunctions:
            raise ValueError(
                "The electrical actuating function already exists in the instrumentation function."
            )
    else:
        if actuating_function in instrumentation_function.actuatingFunctions:
            raise ValueError(
                "The actuating function already exists in the instrumentation function."
            )

    if signal_line.source is not instrumentation_function and signal_line.source is not None:
        raise ValueError("The signal line already has a source.")
    if signal_line.target is not actuating_function and signal_line.target is not None:
        raise ValueError("The signal line already has a target.")

    # Connect signal line
    signal_line.source = instrumentation_function
    signal_line.target = actuating_function

    # Add line and generating function to instrumentation function
    instrumentation_function.signalConveyingFunctions.append(signal_line)
    if is_electrical:
        instrumentation_function.actuatingElectricalFunctions.append(actuating_function)
    else:
        instrumentation_function.actuatingFunctions.append(actuating_function)


def connect_instrumentation_functions(
    source_function: instrumentation.ProcessInstrumentationFunction,
    target_function: instrumentation.ProcessInstrumentationFunction,
    signal_line: instrumentation.SignalLineFunction,
    source_signal_line: bool = True,
):
    """
    Connect two instrumentation functions via a signal line.

    Parameters
    ----------
    source_function : instrumentation.ProcessInstrumentationFunction
        The source instrumentation function that will send the signal.
    target_function : instrumentation.ProcessInstrumentationFunction
        The target instrumentation function that will receive the signal.
    signal_line : instrumentation.SignalLineFunction
        The signal line that conveys the signal from the source to the target function.
    source_signal_line : bool, optional
        If True, the signal line is added to the source function's signalConveyingFunctions.
        If False, the signal line is added to the target function's signalConveyingFunctions.
        Default is True.

    Raises
    ------
    ValueError
        If the signal line already exists in either the source or target function.
        If the signal line already has a source that is not the source function.
        If the signal line already has a target that is not the target function.
    """

    # Some consistency checks
    if (
        signal_line in source_function.signalConveyingFunctions
        or signal_line in target_function.signalConveyingFunctions
    ):
        raise ValueError("The signal line already exists in the instrumentation function.")
    if signal_line.source is not source_function and signal_line.source is not None:
        raise ValueError("The signal line already has a source.")
    if signal_line.target is not target_function and signal_line.target is not None:
        raise ValueError("The signal line already has a target.")

    # Connect signal line
    signal_line.source = source_function
    signal_line.target = target_function

    # Add line and generating function to instrumentation function
    if source_signal_line:
        source_function.signalConveyingFunctions.append(signal_line)
    else:
        target_function.signalConveyingFunctions.append(signal_line)
