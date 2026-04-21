# Review

## Tools panel

The .env-dot span is not centered vertically. It should be.
But I think it is useless, the status could be indicated with the color of the power button.

### Manage tools modal

The items of the version dropdown should have a toggle button "install/uninstall". It should not really be a dropdown in the sens that each item can be installed (selection is not exclusive) and without the menu to close (can install / uninstall multiple version). The "Uninstall version" button does not make sens outside the dropdown.

The info toolbox should always be visible; it should not be at the bottom of the modal which forces the user to scroll down to read the description. The user should not need to scroll, the info box should be on top of the modal (at the bottom).

## Canvas

The drag-n-drop logic for the input pin is not correct. When an input pin is connected, clicking and dragging the pin should change the incoming connection. Instead, it creates a new one, meaning the user can create TWO connections going to the input (which does not make sens!). 

When drag-n-droping a connection to another pin, the old connection should be deleted and a new one should be created. Instead, there is no new connection created.

## Nodes panel

The "Pin" checkbox must be a toggle button with an icon instead of a checkbox with a label. The two icons must be: two arrows to add an input pin, and a cross to delete the input pin. The button must have an explicit tooltip. The button must be before the input label. Update the platform specs and the implementation.

The .p-inputnumber extends beyond its parent. It should be smaller or more on the left to be totally contained within its parent.
The .p-slider-handle is too close to the left edge ; there should be a margin/padding for the slider. Maybe it is related to the CSS margin-inline-start.

The Documentation tab should be opened by default. The plus/minus sign should be replaced by a right/down arrow before the "Documentation" label (.p-panel-title). The documentation should be at the bottom (update the platform specs).

The input field of the output path templates should be initialized with the default. For example the atlas tool output template should be `{input_image.stem}_detections{ext}` by default.