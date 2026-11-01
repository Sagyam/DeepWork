# Bar module

`deepwork bar` prints one line of Waybar-style JSON
(`{"text", "tooltip", "class"}`) and exits. Classes: `active`, `surrendering`,
`upcoming` (a routine within the heads-up window), `nudge`, `idle`, `down`.

Omarchy shell (`~/.config/omarchy/shell.json`, under `bar.layout.<section>`):

```json
{ "id": "deepwork", "type": "command", "exec": "deepwork bar", "interval": 1, "tooltip": "DeepWork" }
```

Waybar:

```jsonc
"custom/deepwork": {
    "exec": "deepwork bar",
    "return-type": "json",
    "interval": 1
}
```
