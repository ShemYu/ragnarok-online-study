extends SceneTree
## Replace a native head SPR; preserve all head/body/equipment ACT records.
## Compatibility entry point (D14): the head slot, template, equipment, fixture action,
## headgear variants and labels are in tools/character-lab/importers/native-head-v1.json;
## the operations are in art_import.gd. Defaults reproduce native-head-v1. Options (unchanged):
##   --output-dir=<pack> --source=<generated board> --costume=<body pack>
##   --palette=<style.json>         indexed adapter (inspection A1-A3)
##   --style-bible=<json>           palette + slot contract; a failing candidate writes nothing
##   --allow-contract-failure       study packs only; the manifest records the failure
##   --recipe=<json> --recipe-module=<id>   provenance written by art_recipe.py
##   --importer-config=<json>       another configuration of the same schema
##   --character-label=<label>      name used in the manifest (default from the configuration)
const ArtImport = preload("res://tools/character-lab/art_import.gd")
const CONFIG := "res://tools/character-lab/importers/native-head-v1.json"

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var options := ArtImport.cli_options()
	quit(ArtImport.run(self, ArtImport.load_config(options.get("importer-config", CONFIG)), options))
