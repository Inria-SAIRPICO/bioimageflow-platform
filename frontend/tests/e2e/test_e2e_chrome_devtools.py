"""
E2E integration tests using chrome-devtools CLI.

Prerequisites:
  - Backend running on port 8000
  - Frontend running on port 5173
  - Chrome open with chrome-devtools daemon started

Run:
  python frontend/tests/e2e/test_e2e_chrome_devtools.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from typing import Any

BASE_URL = "http://localhost:5173"
BACKEND_URL = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_cmd(args: list[str], timeout: int = 30) -> dict[str, Any]:
    """Run a chrome-devtools command and return parsed JSON output."""
    cmd = ["chrome-devtools", *args, "--output-format", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"chrome-devtools {' '.join(args)} failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout}


def run_cmd_text(args: list[str], timeout: int = 30) -> str:
    """Run a chrome-devtools command and return raw text output."""
    cmd = ["chrome-devtools", *args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"chrome-devtools {' '.join(args)} failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result.stdout


def snapshot() -> str:
    """Take an a11y snapshot and return it as text."""
    return run_cmd_text(["take_snapshot"])


def navigate(url: str) -> None:
    """Navigate to a URL and wait for load."""
    run_cmd(["navigate_page", "--url", url])
    time.sleep(2)


def click(uid: str, include_snapshot: bool = False) -> str:
    """Click an element by UID. Returns snapshot text if requested."""
    args = ["click", uid]
    if include_snapshot:
        args.append("--includeSnapshot")
        return run_cmd_text(args)
    run_cmd(args)
    return ""


def fill(uid: str, value: str) -> None:
    """Fill a form element."""
    run_cmd(["fill", uid, value])


def press_key(key: str) -> None:
    """Press a keyboard key."""
    run_cmd(["press_key", key])


def evaluate(script: str) -> Any:
    """Evaluate JavaScript in the page and return the parsed result.

    chrome-devtools returns: {"message": "...\\n```json\\n<VALUE>\\n```"}
    We extract and parse the JSON value from the markdown code block.
    """
    data = run_cmd(["evaluate_script", script])
    msg = data.get("message", "")
    # Extract JSON from markdown code block
    match = re.search(r"```json\n(.*?)\n```", msg, re.DOTALL)
    if match:
        raw = match.group(1).strip()
        if raw == "undefined" or raw == "null":
            return None
        return json.loads(raw)
    # Fallback: try the raw data
    return data


def find_uid(snap: str, text: str) -> str | None:
    """Find the first UID in a snapshot whose line contains `text` (case-insensitive)."""
    target = text.lower()
    for line in snap.split("\n"):
        if target in line.lower() and "uid=" in line:
            for token in line.split():
                if token.startswith("uid="):
                    return token[4:]
    return None


def find_expand_button(snap: str, row_text: str) -> str | None:
    """Find the expand/collapse button UID inside a specific expandable row."""
    lines = snap.split("\n")
    in_target_row = False
    for line in lines:
        if row_text.lower() in line.lower() and "expandable" in line.lower():
            in_target_row = True
        elif in_target_row and "button" in line and "uid=" in line:
            for token in line.split():
                if token.startswith("uid="):
                    return token[4:]
    return None


def find_first_button_in_row(snap: str, row_text: str) -> str | None:
    """Find the first button UID inside a level=2 row matching text."""
    lines = snap.split("\n")
    in_row = False
    for line in lines:
        if row_text.lower() in line.lower() and "level=" in line:
            in_row = True
        elif in_row and "button" in line and "uid=" in line:
            for token in line.split():
                if token.startswith("uid="):
                    return token[4:]
        elif in_row and "row " in line:
            break  # left the row
    return None


def seed_backend() -> dict[str, int]:
    """Call POST /dev/seed to populate test data."""
    result = subprocess.run(
        ["curl", "-s", "-X", "POST", f"{BACKEND_URL}/api/v1/dev/seed"],
        capture_output=True, text=True, timeout=10,
    )
    return json.loads(result.stdout)


def add_node_js(tool_name: str) -> None:
    """Add a tool node via the Vue app's internal API."""
    evaluate(f"""() => {{
        const app = document.querySelector('#app').__vue_app__;
        app._instance.setupState.onAddTool('{tool_name}');
    }}""")
    time.sleep(0.5)


def dispatch_canvas_key(key: str, ctrl: bool = False, shift: bool = False) -> None:
    """Dispatch a keyboard event on the canvas element."""
    evaluate(f"""() => {{
        const canvas = document.querySelector('.canvas-view');
        if (!canvas) return 'no canvas';
        canvas.dispatchEvent(new KeyboardEvent('keydown', {{
            key: '{key}',
            ctrlKey: {str(ctrl).lower()},
            shiftKey: {str(shift).lower()},
            bubbles: true
        }}));
    }}""")
    time.sleep(0.3)


def assert_in(text: str, snap: str, msg: str = "") -> None:
    if text not in snap:
        raise AssertionError(msg or f"Expected '{text}' in snapshot but not found")


def assert_not_in(text: str, snap: str, msg: str = "") -> None:
    if text in snap:
        raise AssertionError(msg or f"Did not expect '{text}' in snapshot but found it")


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_01_app_loads():
    """App loads with ToolsPanel sidebar and Canvas area."""
    print("TEST 01: App loads with ToolsPanel and Canvas")

    navigate(BASE_URL)
    snap = snapshot()

    assert_in("Search tools", snap, "Tools panel search input not found")
    assert_in("Create Tool", snap, "Create Tool button not found")
    assert_in("Name", snap, "TreeTable header 'Name' not found")
    assert_in("Categories", snap, "TreeTable header 'Categories' not found")
    assert_in("Actions", snap, "TreeTable header 'Actions' not found")
    assert_in("Vue Flow mini map", snap, "Canvas mini map not found")
    print("  PASS")


def test_02_seed_and_tools_appear():
    """After seeding, tools and packages appear in the TreeTable."""
    print("TEST 02: Seeded tools appear in TreeTable")

    data = seed_backend()
    assert data["tools"] == 3 and data["packages"] == 2, f"Seed failed: {data}"

    navigate(BASE_URL)
    snap = snapshot()

    assert_in("bioimageflow-cellpose", snap, "cellpose package row not found")
    assert_in("bioimageflow-filters", snap, "filters package row not found")
    assert_in("1.1.0, 1.2.0", snap, "cellpose versions not shown")
    assert_in("stopped", snap, "environment status not shown")
    print("  PASS")


def test_03_expand_package_shows_tools():
    """Expanding a package row reveals its tools with metadata."""
    print("TEST 03: Expanding package shows tools")

    snap = snapshot()
    btn = find_expand_button(snap, "bioimageflow-cellpose")
    assert btn, "Could not find cellpose expand button"

    snap = click(btn, include_snapshot=True)

    assert_in("Cellpose Segmenter", snap, "Cellpose Segmenter not shown after expand")
    assert_in("Segmentation", snap, "Category 'Segmentation' not shown")
    assert_in("segmentation, deep-learning", snap, "Tags not shown")
    assert_in("1.2.0", snap, "Version 1.2.0 not shown")
    print("  PASS")


def test_04_expand_second_package():
    """Expanding filters package reveals GaussianBlur and ThresholdBinarize."""
    print("TEST 04: Expanding second package shows its tools")

    snap = snapshot()
    btn = find_expand_button(snap, "bioimageflow-filters")
    assert btn, "Could not find filters expand button"

    snap = click(btn, include_snapshot=True)

    assert_in("Gaussian Blur", snap, "Gaussian Blur not shown")
    assert_in("Threshold Binarize", snap, "Threshold Binarize not shown")
    assert_in("Preprocessing", snap, "Category 'Preprocessing' not shown")
    print("  PASS")


def test_05_search_filters_tools():
    """Typing in the search box filters tools by name."""
    print("TEST 05: Search filtering works")

    snap = snapshot()
    search_uid = find_uid(snap, 'textbox "Search tools')
    assert search_uid, "Could not find search input UID"

    fill(search_uid, "cellpose")
    time.sleep(0.5)
    snap = snapshot()

    # After filtering, only cellpose package and tool should be visible
    assert_in("bioimageflow-cellpose", snap, "Cellpose package should still be visible")
    assert_not_in("bioimageflow-filters", snap, "Filters package should be filtered out")
    print("  PASS")


def test_06_clear_search_restores_all():
    """Clearing search shows all packages again."""
    print("TEST 06: Clearing search restores all packages")

    snap = snapshot()
    search_uid = find_uid(snap, "textbox")
    assert search_uid, "Could not find search input UID"

    # Clear the search field and wait for Vue reactivity
    evaluate("""() => {
        const input = document.querySelector('[data-testid="tool-search"] input, [data-testid="tool-search"]');
        if (input) {
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeInputValueSetter.call(input, '');
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }""")
    time.sleep(1)
    snap = snapshot()

    assert_in("bioimageflow-cellpose", snap, "cellpose package should reappear")
    assert_in("bioimageflow-filters", snap, "filters package should reappear")
    print("  PASS")


def test_07_add_node_to_canvas():
    """Adding a tool node creates a visible node with correct name."""
    print("TEST 07: Add node to canvas")

    add_node_js("CellposeSegmenter")
    snap = snapshot()

    assert_in("Cellpose Segmenter 1", snap, "Node 'Cellpose Segmenter 1' not found on canvas")
    print("  PASS")


def test_08_node_shows_pins():
    """Tool nodes display input and output pin labels."""
    print("TEST 08: Nodes show input/output pins")

    snap = snapshot()
    # Cellpose inputs: input_image (connectable=True), diameter (connectable=False → no pin)
    # Cellpose outputs: mask, cell_count
    assert_in("input_image", snap, "Input pin 'input_image' not shown")
    assert_in("mask", snap, "Output pin 'mask' not shown")
    assert_in("cell_count", snap, "Output pin 'cell_count' not shown")
    assert_in("ImagePath", snap, "Type badge 'ImagePath' not shown")
    print("  PASS")


def test_09_add_second_node():
    """Adding a different tool creates another node."""
    print("TEST 09: Add second node")

    add_node_js("GaussianBlur")
    snap = snapshot()

    assert_in("Gaussian Blur 1", snap, "Second node 'Gaussian Blur 1' not found")
    assert_in("Cellpose Segmenter 1", snap, "First node should still exist")
    print("  PASS")


def test_10_duplicate_node_increments_name():
    """Adding the same tool again gives it an incremented name."""
    print("TEST 10: Duplicate node gets incremented name")

    add_node_js("CellposeSegmenter")
    snap = snapshot()

    assert_in("Cellpose Segmenter 2", snap, "Second Cellpose should be 'Cellpose Segmenter 2'")
    print("  PASS")


def test_11_node_click_selects():
    """Clicking a node on the canvas selects it."""
    print("TEST 11: Clicking node selects it")

    snap = snapshot()
    node_uid = find_uid(snap, "Cellpose Segmenter 1")
    assert node_uid, "Could not find Cellpose Segmenter 1 node UID"

    click(node_uid)
    time.sleep(0.3)

    selected = evaluate("""() => {
        const els = document.querySelectorAll('.vue-flow__node.selected');
        return els.length;
    }""")
    assert selected >= 1, f"Expected at least 1 selected node, got {selected}"
    print("  PASS")


def test_12_delete_key_removes_node():
    """Selecting and deleting a node removes it from the canvas."""
    print("TEST 12: Delete removes selected node")

    # Select only the Gaussian Blur node via Vue Flow API, then delete
    evaluate("""() => {
        const app = document.querySelector('#app').__vue_app__;
        const canvas = app._instance.refs.canvasRef;
        // Find and select only the Gaussian Blur node
        const nodes = document.querySelectorAll('.vue-flow__node');
        for (const n of nodes) {
            const id = n.getAttribute('data-id');
            if (id && id.startsWith('gaussian_blur')) {
                n.classList.add('selected');
                // Also need to set selected in Vue Flow's internal state
                // Use the node click to trigger Vue Flow selection
                n.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            }
        }
    }""")
    time.sleep(0.5)

    # Now delete the selected node
    evaluate("""() => {
        const app = document.querySelector('#app').__vue_app__;
        const canvas = app._instance.refs.canvasRef;
        if (canvas && canvas.deleteSelected) {
            canvas.deleteSelected();
        }
    }""")
    time.sleep(0.5)

    snap = snapshot()
    # Check the canvas area (after "main") to avoid matching tool panel text
    canvas_area = snap.split("main")[1] if "main" in snap else snap
    assert_not_in("Gaussian Blur 1", canvas_area, "Gaussian Blur 1 should be deleted from canvas")
    assert_in("Cellpose Segmenter 1", canvas_area, "Cellpose Segmenter 1 should still exist")
    assert_in("Cellpose Segmenter 2", canvas_area, "Cellpose Segmenter 2 should still exist")
    print("  PASS")


def test_13_ctrl_a_selects_all():
    """Ctrl+A selects all nodes."""
    print("TEST 13: Ctrl+A select all")

    dispatch_canvas_key("a", ctrl=True)

    count = evaluate("""() => {
        return document.querySelectorAll('.vue-flow__node.selected').length;
    }""")
    assert count == 2, f"Expected 2 selected nodes, got {count}"
    print("  PASS")


def test_14_delete_all_nodes():
    """Delete with all selected removes all nodes."""
    print("TEST 14: Delete all selected nodes")

    dispatch_canvas_key("a", ctrl=True)
    dispatch_canvas_key("Delete")
    time.sleep(0.3)

    snap = snapshot()
    assert_not_in("Cellpose Segmenter", snap.split("main")[1] if "main" in snap else "",
                  "All nodes should be deleted from canvas")
    print("  PASS")


def test_15_api_tools_via_proxy():
    """Frontend can fetch /api/v1/tools through the Vite proxy."""
    print("TEST 15: API /tools endpoint via proxy")

    tools = evaluate("""async () => {
        const resp = await fetch('/api/v1/tools');
        return await resp.json();
    }""")

    assert isinstance(tools, list), f"Expected list, got {type(tools)}"
    assert len(tools) == 3, f"Expected 3 tools, got {len(tools)}"
    names = {t["name"] for t in tools}
    assert "CellposeSegmenter" in names
    assert "GaussianBlur" in names
    assert "ThresholdBinarize" in names
    print("  PASS")


def test_16_api_packages_via_proxy():
    """Frontend can fetch /api/v1/tools/packages through the Vite proxy."""
    print("TEST 16: API /packages endpoint via proxy")

    packages = evaluate("""async () => {
        const resp = await fetch('/api/v1/tools/packages');
        return await resp.json();
    }""")

    assert isinstance(packages, list), f"Expected list, got {type(packages)}"
    assert len(packages) == 2, f"Expected 2 packages, got {len(packages)}"
    names = {p["name"] for p in packages}
    assert "bioimageflow-cellpose" in names
    assert "bioimageflow-filters" in names
    print("  PASS")


def test_17_environment_status():
    """Package rows show environment status (stopped)."""
    print("TEST 17: Environment status displayed on package rows")

    snap = snapshot()
    lines = [l for l in snap.split("\n") if "stopped" in l.lower()]
    assert len(lines) >= 1, "Expected at least one 'stopped' environment status"
    print("  PASS")


def test_18_info_button_toggles_docs():
    """Clicking the info button shows tool documentation."""
    print("TEST 18: Info button shows documentation")

    snap = snapshot()
    # Expand cellpose if collapsed
    if "Cellpose Segmenter" not in snap or "expandable expanded" not in snap:
        btn = find_expand_button(snap, "bioimageflow-cellpose")
        if btn:
            snap = click(btn, include_snapshot=True)

    # Find the info button (first button in the Cellpose Segmenter row)
    info_uid = find_first_button_in_row(snap, "Cellpose Segmenter")
    assert info_uid, "Could not find info button for Cellpose Segmenter"

    snap = click(info_uid, include_snapshot=True)

    assert_in("Segment cells", snap, "Documentation text should appear")
    print("  PASS")


def test_19_canvas_minimap_and_controls():
    """Canvas includes Vue Flow minimap and control buttons."""
    print("TEST 19: Canvas minimap and controls")

    snap = snapshot()
    assert_in("Vue Flow mini map", snap, "Mini map not visible")
    # Count button elements in the main area (zoom controls)
    main_section = snap.split("main")[1] if "main" in snap else snap
    buttons = [l for l in main_section.split("\n") if "button" in l.lower()]
    assert len(buttons) >= 3, f"Expected at least 3 control buttons, found {len(buttons)}"
    print("  PASS")


def test_20_search_by_tag():
    """Search can filter by tag content."""
    print("TEST 20: Search by tag")

    snap = snapshot()
    search_uid = find_uid(snap, "textbox")
    assert search_uid, "Could not find search input"

    fill(search_uid, "deep-learning")
    time.sleep(0.5)
    snap = snapshot()

    assert_in("bioimageflow-cellpose", snap, "Cellpose package should match 'deep-learning' tag")
    assert_not_in("bioimageflow-filters", snap, "Filters should not match 'deep-learning'")

    # Clear search
    fill(search_uid, "")
    time.sleep(0.3)
    print("  PASS")


def test_21_search_by_category():
    """Search can filter by category."""
    print("TEST 21: Search by category")

    snap = snapshot()
    search_uid = find_uid(snap, "textbox")
    assert search_uid, "Could not find search input"

    fill(search_uid, "Preprocessing")
    time.sleep(0.5)
    snap = snapshot()

    assert_in("bioimageflow-filters", snap, "Filters package should match 'Preprocessing' category")
    assert_not_in("bioimageflow-cellpose", snap, "Cellpose should not match 'Preprocessing'")

    # Clear search
    fill(search_uid, "")
    time.sleep(0.3)
    print("  PASS")


def test_22_node_add_and_connect():
    """Two compatible nodes can be connected (verified via JS)."""
    print("TEST 22: Node connection validation")

    # Add two nodes with compatible types
    add_node_js("GaussianBlur")
    add_node_js("CellposeSegmenter")
    time.sleep(0.5)

    # Verify connection validation via the exposed isValidConnection method
    valid = evaluate("""() => {
        const nodes = document.querySelectorAll('.vue-flow__node');
        if (nodes.length < 2) return 'not enough nodes: ' + nodes.length;

        // Access the CanvasView component via the template ref
        const app = document.querySelector('#app').__vue_app__;
        const canvasRef = app._instance.refs.canvasRef;
        if (!canvasRef || !canvasRef.isValidConnection) return 'no canvas ref';

        // Get node IDs from the DOM
        const nodeIds = Array.from(nodes).map(n => n.getAttribute('data-id'));

        // Find GaussianBlur and CellposeSegmenter nodes
        let gaussianId = null, cellposeId = null;
        for (const id of nodeIds) {
            if (id && id.startsWith('gaussian_blur')) gaussianId = id;
            if (id && id.startsWith('cellpose_segmenter')) cellposeId = id;
        }
        if (!gaussianId || !cellposeId) return 'node ids not found: ' + JSON.stringify(nodeIds);

        // GaussianBlur output_image (ImagePath) -> CellposeSegmenter input_image (ImagePath)
        return canvasRef.isValidConnection({
            source: gaussianId,
            target: cellposeId,
            sourceHandle: 'output_image',
            targetHandle: 'input_image'
        });
    }""")
    assert valid is True, f"Expected valid connection, got {valid}"
    print("  PASS")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

ALL_TESTS = [
    test_01_app_loads,
    test_02_seed_and_tools_appear,
    test_03_expand_package_shows_tools,
    test_04_expand_second_package,
    test_05_search_filters_tools,
    test_06_clear_search_restores_all,
    test_07_add_node_to_canvas,
    test_08_node_shows_pins,
    test_09_add_second_node,
    test_10_duplicate_node_increments_name,
    test_11_node_click_selects,
    test_12_delete_key_removes_node,
    test_13_ctrl_a_selects_all,
    test_14_delete_all_nodes,
    test_15_api_tools_via_proxy,
    test_16_api_packages_via_proxy,
    test_17_environment_status,
    test_18_info_button_toggles_docs,
    test_19_canvas_minimap_and_controls,
    test_20_search_by_tag,
    test_21_search_by_category,
    test_22_node_add_and_connect,
]


def main():
    print("=" * 60)
    print("BioImageFlow E2E Tests (chrome-devtools CLI)")
    print(f"  Backend: {BACKEND_URL}")
    print(f"  Frontend: {BASE_URL}")
    print("=" * 60)
    print()

    # Verify chrome-devtools is running
    status = subprocess.run(
        ["chrome-devtools", "status"], capture_output=True, text=True
    )
    if "not running" in status.stdout:
        print("Starting chrome-devtools daemon...")
        subprocess.run(["chrome-devtools", "start"], capture_output=True, text=True)
        time.sleep(2)

    passed = 0
    failed = 0
    errors: list[str] = []

    for test_fn in ALL_TESTS:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            failed += 1
            errors.append(f"FAIL: {test_fn.__name__}: {e}")
            print(f"  FAIL: {e}")
        except Exception as e:
            failed += 1
            errors.append(f"ERROR: {test_fn.__name__}: {type(e).__name__}: {e}")
            print(f"  ERROR: {type(e).__name__}: {e}")

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(ALL_TESTS)} tests")
    print("=" * 60)

    if errors:
        print()
        print("Failures:")
        for err in errors:
            print(f"  - {err}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
