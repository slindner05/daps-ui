from flask import Blueprint, jsonify, render_template, send_from_directory
from daps_webui import db, models
from pathlib import Path
import re

poster_renamer = Blueprint("poster_renamer", __name__)


@poster_renamer.route("/poster-renamer")
def poster_renamer_route():
    return render_template("poster_renamer/poster_renamer.html")


@poster_renamer.route("/serve-image/<path:filename>", methods=["GET"])
def serve_image(filename):
    settings = models.Settings.query.first()
    asset_folders = getattr(settings, "asset_folders", False)
    assets_directory = getattr(settings, "target_path", "")
    if not assets_directory:
        return (
            jsonify({"success": False, "message": "No target path found in settings."}),
            500,
        )
    try:
        if asset_folders:
            parent_dir, name = filename.split("/", 1)
            file_path = f"{parent_dir}/{name}"
        else:
            file_path = filename

        return send_from_directory(assets_directory, file_path)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@poster_renamer.route("/poster-renamer/get-file-paths", methods=["GET"])
def get_images():
    try:
        settings = models.Settings.query.first()
        asset_folders = getattr(settings, "asset_folders", False)
        assets_directory = getattr(settings, "target_path", "")
        if not assets_directory:
            return (
                jsonify(
                    {"success": False, "message": "No target path found in settings."}
                ),
                500,
            )

        file_cache_entries = models.FileCache.query.all()
        sorted_files = {"movies": [], "shows": {}, "collections": []}

        if asset_folders:
            season_pattern = re.compile(r"^Season(?P<season>\d{2}).(?P<ext>\w+)$")
            show_pattern = re.compile(r"^Poster.\w+$")
        else:
            season_pattern = re.compile(
                r"^(?P<name>.+ \(\d{4}\))_Season(?P<season>\d{2}).(?P<ext>\w+)$"
            )
            show_pattern = re.compile(r"^(?P<name>.+ \(\d{4}\)).(?P<ext>\w+)$")

        shows_dict = {}

        for file in file_cache_entries:
            file_name = Path(file.file_path).name
            parent_dir = Path(file.file_path).parent.name
            match = re.match(r"^(?P<name>.+ \(\d{4}\))", parent_dir)

            if match:
                parent_dir_stripped = match.group("name").strip()
            else:
                parent_dir_stripped = parent_dir

            file_data = {
                "file_name": parent_dir if asset_folders else file_name,
                "file_path": (
                    f"/serve-image/{parent_dir}/{file_name}"
                    if asset_folders
                    else f"/serve-image/{file_name}"
                ),
                "source_path": file.source_path,
                "file_hash": file.file_hash,
            }
            if file.media_type == "movies":
                sorted_files["movies"].append(file_data)
            elif file.media_type == "collections":
                sorted_files["collections"].append(file_data)
            else:
                show_match = show_pattern.match(file_name)
                season_match = season_pattern.match(file_name)
                if show_match:
                    show_name = (
                        parent_dir_stripped
                        if asset_folders
                        else show_match.group("name")
                    )
                    if show_name not in shows_dict:
                        shows_dict[show_name] = {
                            "file_name": show_name,
                            "file_path": (
                                f"/serve-image/{parent_dir}/{file_name}"
                                if asset_folders
                                else f"/serve-image/{file_name}"
                            ),
                            "source_path": file.source_path,
                            "file_hash": file.file_hash,
                            "seasons": [],
                        }
                if season_match:
                    show_name = (
                        parent_dir_stripped
                        if asset_folders
                        else season_match.group("name")
                    )
                    season_number = int(season_match.group("season"))
                    if show_name in shows_dict:
                        shows_dict[show_name]["seasons"].append(
                            {
                                "season": season_number,
                                "source_path": file.source_path,
                                "file_hash": file.file_hash,
                                "file_path": (
                                    f"/serve-image/{parent_dir}/{file_name}"
                                    if asset_folders
                                    else f"/serve-image/{file_name}"
                                ),
                            }
                        )

        for show in sorted_files["shows"].values():
            show["seasons"].sort(key=lambda s: s["season"])
        sorted_files["movies"] = sorted(
            sorted_files["movies"], key=lambda x: x["file_name"]
        )
        sorted_files["collections"] = sorted(
            sorted_files["collections"], key=lambda x: x["file_name"]
        )
        sorted_files["shows"] = dict(sorted(shows_dict.items(), key=lambda x: x[0]))

        return jsonify({"success": True, "sorted_files": sorted_files})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
