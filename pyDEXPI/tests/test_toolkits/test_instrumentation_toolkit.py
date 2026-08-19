import pytest

from pydexpi.dexpi_classes import instrumentation
from pydexpi.toolkits import instrumentation_toolkit as it


def test_add_signal_generating_function_to_instrumentation_function():
    """Test adding a signal generating function to a process instrumentation function."""
    # Create a new instrumentation function
    instr_func = instrumentation.ProcessInstrumentationFunction()
    signal_gen = instrumentation.ProcessSignalGeneratingFunction()
    measuring_line = instrumentation.MeasuringLineFunction()

    # Add the signal generating function to the instrumentation function
    it.add_signal_generating_function_to_instrumentation_function(
        instr_func, signal_gen, measuring_line
    )

    # Check that the function was added correctly
    assert measuring_line in instr_func.signalConveyingFunctions
    assert signal_gen in instr_func.processSignalGeneratingFunctions
    assert measuring_line.source == signal_gen
    assert measuring_line.target == instr_func

    # Test error cases
    # Case 1: Measuring line already exists in the instrumentation function
    with pytest.raises(ValueError):
        it.add_signal_generating_function_to_instrumentation_function(
            instr_func, instrumentation.ProcessSignalGeneratingFunction(), measuring_line
        )

    # Case 2: Signal generating function already exists in the instrumentation function
    new_measuring_line = instrumentation.MeasuringLineFunction()
    with pytest.raises(ValueError):
        it.add_signal_generating_function_to_instrumentation_function(
            instr_func, signal_gen, new_measuring_line
        )

    # Case 3: Measuring line already has a source that is not the signal generating function
    new_measuring_line = instrumentation.MeasuringLineFunction()
    new_signal_gen = instrumentation.ProcessSignalGeneratingFunction()
    new_measuring_line.source = new_signal_gen
    with pytest.raises(ValueError):
        it.add_signal_generating_function_to_instrumentation_function(
            instr_func, instrumentation.ProcessSignalGeneratingFunction(), new_measuring_line
        )

    # Case 4: Measuring line already has a target that is not the instrumentation function
    new_measuring_line = instrumentation.MeasuringLineFunction()
    new_instr_func = instrumentation.ProcessInstrumentationFunction()
    new_measuring_line.target = new_instr_func
    with pytest.raises(ValueError):
        it.add_signal_generating_function_to_instrumentation_function(
            instr_func, instrumentation.ProcessSignalGeneratingFunction(), new_measuring_line
        )


def test_add_signal_opc_to_instrumentation_function():
    """Test adding a signal off-page connector to an instrumentation function."""
    # Create a new instrumentation function
    instr_func = instrumentation.ProcessInstrumentationFunction()

    # Test outgoing signal OPC
    outgoing_opc = instrumentation.FlowOutSignalOffPageConnector()
    outgoing_line = instrumentation.SignalLineFunction()

    it.add_signal_opc_to_instrumentation_function(instr_func, outgoing_opc, outgoing_line)

    # Check that the function was added correctly for outgoing signal
    assert outgoing_line in instr_func.signalConveyingFunctions
    assert outgoing_opc in instr_func.signalConnectors
    assert outgoing_line.source == instr_func
    assert outgoing_line.target == outgoing_opc

    # Test incoming signal OPC
    incoming_opc = instrumentation.FlowInSignalOffPageConnector()  # base class is used for incoming
    incoming_line = instrumentation.SignalLineFunction()

    it.add_signal_opc_to_instrumentation_function(instr_func, incoming_opc, incoming_line)

    # Check that the function was added correctly for incoming signal
    assert incoming_line in instr_func.signalConveyingFunctions
    assert incoming_opc in instr_func.signalConnectors
    assert incoming_line.source == incoming_opc
    assert incoming_line.target == instr_func

    # Test error cases
    # Case 1: Signal OPC already exists in the instrumentation function
    with pytest.raises(ValueError):
        it.add_signal_opc_to_instrumentation_function(
            instr_func, outgoing_opc, instrumentation.SignalLineFunction()
        )

    # Case 2: Signal line already exists in the instrumentation function
    with pytest.raises(ValueError):
        it.add_signal_opc_to_instrumentation_function(
            instr_func, instrumentation.FlowOutSignalOffPageConnector(), outgoing_line
        )

    # Case 3: Signal line already has a target (for outgoing signals)
    new_outgoing_line = instrumentation.SignalLineFunction()
    new_outgoing_line.target = instrumentation.FlowOutSignalOffPageConnector()
    with pytest.raises(ValueError):
        it.add_signal_opc_to_instrumentation_function(
            instr_func, instrumentation.FlowOutSignalOffPageConnector(), new_outgoing_line
        )

    # Case 4: Signal line already has a source (for incoming signals)
    new_incoming_line = instrumentation.SignalLineFunction()
    new_incoming_line.source = instrumentation.FlowInSignalOffPageConnector()
    with pytest.raises(ValueError):
        it.add_signal_opc_to_instrumentation_function(
            instr_func, instrumentation.FlowInSignalOffPageConnector(), new_incoming_line
        )


def test_add_actuating_function_to_instrumentation_function():
    """Test adding an actuating function to an instrumentation function."""
    # Create a new instrumentation function
    instr_func = instrumentation.ProcessInstrumentationFunction()

    # Test regular actuating function
    actuating_func = instrumentation.ActuatingFunction()
    signal_line = instrumentation.SignalLineFunction()

    it.add_actuating_function_to_instrumentation_function(instr_func, actuating_func, signal_line)

    # Check that the function was added correctly
    assert signal_line in instr_func.signalConveyingFunctions
    assert actuating_func in instr_func.actuatingFunctions
    assert signal_line.source == instr_func
    assert signal_line.target == actuating_func

    # Test electrical actuating function
    elect_actuating_func = instrumentation.ActuatingElectricalFunction()
    elect_signal_line = instrumentation.SignalLineFunction()

    it.add_actuating_function_to_instrumentation_function(
        instr_func, elect_actuating_func, elect_signal_line
    )

    # Check that the electrical function was added correctly
    assert elect_signal_line in instr_func.signalConveyingFunctions
    assert elect_actuating_func in instr_func.actuatingElectricalFunctions
    assert elect_signal_line.source == instr_func
    assert elect_signal_line.target == elect_actuating_func

    # Test error cases
    # Case 1: Signal line already exists in the instrumentation function
    with pytest.raises(ValueError):
        it.add_actuating_function_to_instrumentation_function(
            instr_func, instrumentation.ActuatingFunction(), signal_line
        )

    # Case 2: Actuating function already exists in the instrumentation function
    new_signal_line = instrumentation.SignalLineFunction()
    with pytest.raises(ValueError):
        it.add_actuating_function_to_instrumentation_function(
            instr_func, actuating_func, new_signal_line
        )

    # Case 3: Electrical actuating function already exists in the instrumentation function
    new_elect_signal_line = instrumentation.SignalLineFunction()
    with pytest.raises(ValueError):
        it.add_actuating_function_to_instrumentation_function(
            instr_func, elect_actuating_func, new_elect_signal_line
        )

    # Case 4: Signal line already has a source that is not the instrumentation function
    new_signal_line = instrumentation.SignalLineFunction()
    new_signal_line.source = instrumentation.ProcessInstrumentationFunction()
    with pytest.raises(ValueError):
        it.add_actuating_function_to_instrumentation_function(
            instr_func, instrumentation.ActuatingFunction(), new_signal_line
        )

    # Case 5: Signal line already has a target that is not the actuating function
    new_signal_line = instrumentation.SignalLineFunction()
    new_signal_line.target = instrumentation.ActuatingFunction()
    with pytest.raises(ValueError):
        it.add_actuating_function_to_instrumentation_function(
            instr_func, instrumentation.ActuatingFunction(), new_signal_line
        )


def test_connect_instrumentation_functions():
    """Test connecting two instrumentation functions via a signal line."""
    # Create two instrumentation functions
    source_func = instrumentation.ProcessInstrumentationFunction()
    target_func = instrumentation.ProcessInstrumentationFunction()
    signal_line = instrumentation.SignalLineFunction()

    # Connect the functions with source_signal_line=True
    it.connect_instrumentation_functions(
        source_func, target_func, signal_line, source_signal_line=True
    )

    # Check that the functions were connected correctly
    assert signal_line in source_func.signalConveyingFunctions
    assert signal_line not in target_func.signalConveyingFunctions
    assert signal_line.source == source_func
    assert signal_line.target == target_func

    # Connect two other functions with source_signal_line=False
    source_func2 = instrumentation.ProcessInstrumentationFunction()
    target_func2 = instrumentation.ProcessInstrumentationFunction()
    signal_line2 = instrumentation.SignalLineFunction()

    it.connect_instrumentation_functions(
        source_func2, target_func2, signal_line2, source_signal_line=False
    )

    # Check that the functions were connected correctly
    assert signal_line2 not in source_func2.signalConveyingFunctions
    assert signal_line2 in target_func2.signalConveyingFunctions
    assert signal_line2.source == source_func2
    assert signal_line2.target == target_func2

    # Test error cases
    # Case 1: Signal line already exists in the source function
    new_signal_line = instrumentation.SignalLineFunction()
    source_func3 = instrumentation.ProcessInstrumentationFunction()
    target_func3 = instrumentation.ProcessInstrumentationFunction()
    source_func3.signalConveyingFunctions.append(new_signal_line)

    with pytest.raises(ValueError):
        it.connect_instrumentation_functions(source_func3, target_func3, new_signal_line)

    # Case 2: Signal line already exists in the target function
    new_signal_line = instrumentation.SignalLineFunction()
    source_func4 = instrumentation.ProcessInstrumentationFunction()
    target_func4 = instrumentation.ProcessInstrumentationFunction()
    target_func4.signalConveyingFunctions.append(new_signal_line)

    with pytest.raises(ValueError):
        it.connect_instrumentation_functions(source_func4, target_func4, new_signal_line)

    # Case 3: Signal line already has a source that is not the source function
    new_signal_line = instrumentation.SignalLineFunction()
    new_signal_line.source = instrumentation.ProcessInstrumentationFunction()

    with pytest.raises(ValueError):
        it.connect_instrumentation_functions(source_func, target_func, new_signal_line)

    # Case 4: Signal line already has a target that is not the target function
    new_signal_line = instrumentation.SignalLineFunction()
    new_signal_line.target = instrumentation.ProcessInstrumentationFunction()

    with pytest.raises(ValueError):
        it.connect_instrumentation_functions(source_func, target_func, new_signal_line)
