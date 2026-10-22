# Tools

Helpers for maintaining this repository. You do not need them to run the workshop.

| File | What it does |
| --- | --- |
| `term_screenshot.py` | Renders captured terminal output as a PNG with headless Chrome or Chromium. Used for the images in `docs/images/`. |

## Make a terminal screenshot

Capture the real output with `tee`, then render it:

```bash
python3 environment/check_setup.py 2>&1 | tee /tmp/check.log
python3 tools/term_screenshot.py --log /tmp/check.log \
    --command "python3 environment/check_setup.py" --title "Setup check" \
    --out docs/images/01-setup-check.png
```

Status words such as `[pass]` and `READY` are colored in the image, but each one is still a word, so the meaning never depends on color.

When you add a screenshot to a README, write alt text that includes the important text shown in the image.
