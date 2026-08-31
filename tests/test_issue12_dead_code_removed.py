"""
Issue #12: removed unreachable processor hooks (insert_global_processor_hook/
generate_processor, no callers), disabled drag-and-drop code in
TableWidgetDragRows (string-literal dead code), and the unused
Rectangle/Point helper classes in rectangle_selector.py (capture region
selection uses RectangleSelector/QRectF exclusively). as64processes/lblj.py
was deliberately left in place - reviving it is being considered separately.
"""
import as64core.processing as processing


def test_unreachable_processor_hooks_are_gone():
    assert not hasattr(processing, "insert_global_processor_hook")
    assert not hasattr(processing, "generate_processor")
    assert not hasattr(processing, "subprocess_hooks")


def test_processing_still_exposes_live_api():
    # Make sure we didn't remove anything that's actually used.
    assert hasattr(processing, "register_process")
    assert hasattr(processing, "insert_global_hook")
    assert hasattr(processing, "ProcessorGenerator")


def test_unused_rectangle_point_classes_are_gone():
    import as64gui.graphics.rectangle_selector as rectangle_selector
    assert not hasattr(rectangle_selector, "Rectangle")
    assert not hasattr(rectangle_selector, "Point")

    import as64gui.graphics as graphics
    assert not hasattr(graphics, "Rectangle")


def test_rectangle_selector_still_exported():
    import as64gui.graphics as graphics
    assert hasattr(graphics, "RectangleSelector")


def test_table_widget_drag_rows_still_instantiable(qapp):
    from as64gui.widgets.table_widget import TableWidgetDragRows

    widget = TableWidgetDragRows()
    assert widget.selectionMode() == widget.ExtendedSelection
    # The disabled dropEvent/drop_on/is_below trio should no longer exist as methods.
    assert not hasattr(widget, "drop_on")
    assert not hasattr(widget, "is_below")

    # lblj.py is intentionally kept, unregistered, pending a decision on reviving it.
    from as64processes import lblj
    assert hasattr(lblj, "ProcessLBLJ")
    assert hasattr(lblj, "ProcessLBLJ2")
