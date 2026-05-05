# Review

## Menus

## Docks

## Workflows

## Data table

## Tools panel

## Tool Creation

The tools must be created in there own folder. The folder should contain the 

## Code Editor


### Manage tools dialog


## Canvas



## Nodes panel


## Top menu bar

## Logs

The following button has no icon, and is not visible:
<button data-v-198265c5="" class="p-button p-component p-button-icon-only p-button-secondary p-button-text p-button-outlined logger-panel__auto-scope--inactive" data-p="icon-only outlined text" type="button" aria-label="Auto-scope to selected node" data-pc-name="button" data-p-disabled="false" data-testid="log-auto-scope" pc6="" data-pc-section="root" data-p-severity="secondary"><span class="p-button-icon pi pi-unlink" data-p="left" data-pc-section="icon"></span><!----><!----></button>

During execution, the outputs of a tool are not labelled properly. They appear in the global logs, but not the logs of the tool.
For example executing a workflow with an Atlas node shows those logs (unfiltered):

15:18:39.660 INF Execution started for atlas_1
15:18:39.735 INF Wetlands initialized at /Users/amasson/.bioimageflow/wetlands
15:18:39.736 INF Files 1 Node files_1 used cached result
15:18:39.741 INF Atlas 1 Node atlas_1 started
15:18:39.747 INF Creating Wetlands environment 'atlas' (max_workers=1, worker_timeout=None)
15:18:39.747 INF Loading existing environment 'atlas' from '/Users/amasson/.bioimageflow/wetlands/pixi/workspaces/atlas/pixi.toml'
15:18:40.795 INF Listening port 65321
15:18:40.812 INF 2026-05-04 15:18:40,812 INFO:7850:atlas:Execute /Users/amasson/Travail/bioimageflow/packages/bioimageflow-core/bioimageflow_core/worker.py:run_process_row((('/Users/amasson/.bioimageflow/tool_packages/bioimageflow_common_tools/0.1.3/bioimageflow_common_tools/atlas.py', 'Atlas', {'input_image': '/Users/amasson/.bioimageflow/datasets/20260421T161116_fish_13432_seg.tiff', 'area_lim': 0, 'gaussian_std': 25, 'p_value': 0.02, 'verbose': False, 'output_image': 'bif_data/workflows/Untitled_2/data/atlas_1/20260504_151839_c36c7cbf57e1/assets/20260421T161116_fish_13432_seg_detections.tiff'}, {'run_dir': 'bif_data/workflows/Untitled_2/data/atlas_1/20260504_151839_c36c7cbf57e1', 'assets_dir': 'bif_data/workflows/Untitled_2/data/atlas_1/20260504_151839_c36c7cbf57e1/assets', 'work_dir': 'bif_data/workflows/Untitled_2/data/atlas_1/20260504_151839_c36c7cbf57e1/work/rows/000000_0_b6589fc6', 'rows_dir': 'bif_data/workflows/Untitled_2/data/atlas_1/20260504_151839_c36c7cbf57e1/work/rows', 'row_index': '0'}),))
15:18:40.817 INF Running Atlas spot detection on 20260421T161116_fish_13432_seg.tiff...
15:18:40.882 INF OMP: Info #276: omp_set_nested routine deprecated, please use omp_set_max_active_levels instead.
15:18:41.329 INF 1.000000	0.000832	1044484	0.000011	1.000000
15:18:41.329 INF 1.200000	0.000581	1044484	0.000147	1.000000
15:18:41.329 INF 1.440000	0.000393	1044484	0.000534	0.000000
15:18:41.329 INF 1.728000	0.000278	1044484	0.000182	1.000000
15:18:41.329 INF 2.073600	0.000206	1044484	0.000097	1.000000
15:18:41.329 INF 2.488320	0.000165	1040400	0.000228	0.000001
15:18:41.329 INF 2.985985	0.000140	1040400	0.000161	0.040837
15:18:41.329 INF 3.583182	0.000114	1040400	0.000069	0.999999
15:18:41.329 INF 4.299818	0.000098	1040400	0.000160	0.000000
15:18:41.329 INF 5.159782	0.000082	1040400	0.000200	-0.000000
15:18:41.329 INF 6.191739	0.000075	1040400	0.000145	0.000000
15:18:41.329 INF 7.430087	0.000059	1036324	0.000038	0.999054
15:18:41.329 INF 8.916104	0.000052	1036324	0.000128	-0.000000
15:18:41.329 INF 10.699326	0.000043	1036324	0.000087	0.000000
15:18:41.329 INF 12.839191	0.000036	1032256	0.000049	0.016686
15:18:41.329 INF 15.407030	0.000031	1032256	0.000120	-0.000000
15:18:41.330 INF 18.488438	0.000025	1032256	0.000045	0.000248
15:18:41.330 INF 22.186127	0.000021	1028196	0.000022	0.390825
15:18:41.330 INF 26.623354	0.000021	1028196	0.000026	0.131976
15:18:41.330 INF 31.948027	0.000019	1024144	0.000013	0.939439
15:18:41.330 INF Selected scale: 5.159782
15:18:41.336 INF Atlas: detection complete -> 20260421T161116_fish_13432_seg_detections.tiff
15:18:41.337 INF 2026-05-04 15:18:41,336 INFO:7850:atlas:Executed
15:18:41.338 INF 2026-05-04 15:18:41,338 INFO:7850:atlas:Execute /Users/amasson/Travail/bioimageflow/packages/bioimageflow-core/bioimageflow_core/worker.py:run_process_row((('/Users/amasson/.bioimageflow/tool_packages/bioimageflow_common_tools/0.1.3/bioimageflow_common_tools/atlas.py', 'Atlas', {'input_image': '/Users/amasson/.bioimageflow/datasets/20260421T161138_img02_seg.tiff', 'area_lim': 0, 'gaussian_std': 25, 'p_value': 0.02, 'verbose': False, 'output_image': 'bif_data/workflows/Untitled_2/data/atlas_1/20260504_151839_c36c7cbf57e1/assets/20260421T161138_img02_seg_detections.tiff'}, {'run_dir': 'bif_data/workflows/Untitled_2/data/atlas_1/20260504_151839_c36c7cbf57e1', 'assets_dir': 'bif_data/workflows/Untitled_2/data/atlas_1/20260504_151839_c36c7cbf57e1/assets', 'work_dir': 'bif_data/workflows/Untitled_2/data/atlas_1/20260504_151839_c36c7cbf57e1/work/rows/000001_1_356a192b', 'rows_dir': 'bif_data/workflows/Untitled_2/data/atlas_1/20260504_151839_c36c7cbf57e1/work/rows', 'row_index': '1'}),))
15:18:41.338 INF Running Atlas spot detection on 20260421T161138_img02_seg.tiff...
15:18:41.370 INF OMP: Info #276: omp_set_nested routine deprecated, please use omp_set_max_active_levels instead.
15:18:41.452 INF 1.200000	0.000581	161355	0.000112	1.000000
15:18:41.452 INF 1.440000	0.000393	161355	0.001500	0.000000
15:18:41.452 INF 1.728000	0.000278	161355	0.000744	0.000000
15:18:41.452 INF 2.073600	0.000206	161355	0.000130	0.990427
15:18:41.452 INF 2.488320	0.000165	159735	0.001202	0.000000
15:18:41.452 INF 2.985985	0.000140	159735	0.000507	-0.000000
15:18:41.453 INF 3.583182	0.000114	159735	0.000175	0.020118
15:18:41.453 INF 4.299818	0.000098	159735	0.000038	0.998204
15:18:41.453 INF 5.159782	0.000082	159735	0.000050	0.950202
15:18:41.453 INF 6.191739	0.000075	159735	0.000069	0.646146
15:18:41.453 INF 7.430087	0.000059	158123	0.000013	0.999104
15:18:41.453 INF 8.916104	0.000052	158123	0.000051	0.568256
15:18:41.453 INF 10.699326	0.000043	158123	0.000006	0.998896
15:18:41.453 INF 12.839191	0.000036	156519	0.000006	0.996340
15:18:41.453 INF 15.407030	0.000031	156519	0.000077	0.004338
15:18:41.453 INF 18.488438	0.000025	156519	0.000077	0.000810
15:18:41.454 INF 22.186127	0.000021	154923	0.000058	0.005947
15:18:41.454 INF 26.623354	0.000021	154923	0.000116	0.000000
15:18:41.454 INF 31.948027	0.000019	153335	0.000124	0.000000
15:18:41.454 INF Selected scale: 2.985985
15:18:41.454 INF Atlas: detection complete -> 20260421T161138_img02_seg_detections.tiff
15:18:41.454 INF 2026-05-04 15:18:41,454 INFO:7850:atlas:Executed
15:18:41.454 INF Atlas 1 Node atlas_1 completed row 0/2
15:18:41.454 INF Atlas 1 Node atlas_1 completed row 1/2
15:18:41.455 INF Atlas 1 Node atlas_1 completed
15:18:41.480 INF 2026-05-04 15:18:41,480 INFO:7850:atlas:exit
15:18:41.497 INF Workflow execution completed successfully

But when filtering logs to keep only "Atlas 1" I get:

15:18:39.741 INF Atlas 1 Node atlas_1 started
15:18:41.454 INF Atlas 1 Node atlas_1 completed row 0/2
15:18:41.454 INF Atlas 1 Node atlas_1 completed row 1/2
15:18:41.455 INF Atlas 1 Node atlas_1 completed

I should get all Atlas output like:

15:18:40.817 INF Running Atlas spot detection on 20260421T161116_fish_13432_seg.tiff...
15:18:40.882 INF OMP: Info #276: omp_set_nested routine deprecated, please use omp_set_max_active_levels instead.
15:18:41.329 INF 1.000000	0.000832	1044484	0.000011	1.000000
15:18:41.329 INF 1.200000	0.000581	1044484	0.000147	1.000000
15:18:41.329 INF 1.440000	0.000393	1044484	0.000534	0.000000
15:18:41.329 INF 1.728000	0.000278	1044484	0.000182	1.000000
15:18:41.329 INF 2.073600	0.000206	1044484	0.000097	1.000000
...

## Errors

When an error occur, it is displayed where the progress bar is ; but the error added to the Error history has less information. Errors should appear in the Logger.
The Error history should either point to the error in the logger, or open a dialog with the full details.

## Others
