from pathlib import Path

from bioimageflow_server.services.output_views import remove_latest_node_outputs


def test_remove_latest_node_outputs_removes_only_requested_scoped_node(tmp_path: Path) -> None:
    requested_pointer = (
        tmp_path / "views" / "latest" / "group" / "selected.bioimageflow-link.json"
    )
    surviving_pointer = tmp_path / "views" / "latest" / "survivor.bioimageflow-link.json"
    legacy_pointer = tmp_path / "latest" / "group" / "selected.bioimageflow-link.json"
    requested_output = tmp_path / "outputs" / "latest" / "group" / "selected"
    surviving_output = tmp_path / "outputs" / "latest" / "survivor"
    for path in (requested_pointer, surviving_pointer, legacy_pointer):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
    for path in (requested_output, surviving_output):
        path.mkdir(parents=True)
        (path / "dataframe.csv").write_text("value\n1\n")

    remove_latest_node_outputs(tmp_path, ["group/selected"])

    assert not requested_pointer.exists()
    assert not legacy_pointer.exists()
    assert not requested_output.exists()
    assert surviving_pointer.exists()
    assert surviving_output.exists()
