import socket

import requests
from flask import Blueprint, jsonify, render_template, request

from daps_webui import db, models
from DapsEX.settings import Settings

settings = Blueprint("settings", __name__)


@settings.route("/settings", methods=["GET"])
def settings_route():
    return render_template("settings/settings.html")


@settings.route("/get-settings", methods=["GET"])
def get_settings():
    try:
        settings = models.Settings.query.first()
        radarr_instances = models.RadarrInstance.query.all()
        sonarr_instances = models.SonarrInstance.query.all()
        plex_instances = models.PlexInstance.query.all()
        gdrives = models.GDrives.query.all()
        rclone = models.RCloneConf.query.first()

        data = {
            "logLevelUnmatchedAssets": getattr(
                settings, "log_level_unmatched_assets", ""
            ),
            "logLevelPosterRenamer": getattr(settings, "log_level_poster_renamer", ""),
            "logLevelPlexUploaderr": getattr(settings, "log_level_plex_uploaderr", ""),
            "logLevelBorderReplacerr": getattr(
                settings, "log_level_border_replacerr", ""
            ),
            "logLevelDriveSync": getattr(settings, "log_level_drive_sync", ""),
            "posterRenamerSchedule": getattr(settings, "poster_renamer_schedule", ""),
            "unmatchedAssetsSchedule": getattr(
                settings, "unmatched_assets_schedule", ""
            ),
            "plexUploaderrSchedule": getattr(settings, "plex_uploaderr_schedule", ""),
            "driveSyncSchedule": getattr(settings, "drive_sync_schedule", ""),
            "targetPath": getattr(settings, "target_path", ""),
            "sourceDirs": (
                getattr(settings, "source_dirs", "").split(",")
                if getattr(settings, "source_dirs", "")
                else []
            ),
            "libraryNames": (
                getattr(settings, "library_names", "").split(",")
                if getattr(settings, "library_names", "")
                else []
            ),
            "instances": (
                getattr(settings, "instances", "").split(",")
                if getattr(settings, "instances", "")
                else []
            ),
            "assetFolders": getattr(settings, "asset_folders", False),
            "cleanAssets": getattr(settings, "clean_assets", False),
            "unmatchedAssets": getattr(settings, "unmatched_assets", True),
            "replaceBorder": getattr(settings, "replace_border", False),
            "borderSetting": getattr(settings, "border_setting", False),
            "customColor": getattr(settings, "custom_color", ""),
            "runSingleItem": getattr(settings, "run_single_item", False),
            "onlyUnmatched": getattr(settings, "only_unmatched", False),
            "uploadToPlex": getattr(settings, "upload_to_plex", False),
            "matchAlt": getattr(settings, "match_alt", False),
            "reapplyPosters": getattr(settings, "reapply_posters", False),
            "showAllUnmatched": getattr(settings, "show_all_unmatched", False),
            "disableUnmatchedCollections": getattr(
                settings, "disable_unmatched_collections", False
            ),
            "radarrInstances": [
                {
                    "instanceName": instance.instance_name,
                    "url": instance.url,
                    "apiKey": instance.api_key,
                }
                for instance in radarr_instances
            ],
            "sonarrInstances": [
                {
                    "instanceName": instance.instance_name,
                    "url": instance.url,
                    "apiKey": instance.api_key,
                }
                for instance in sonarr_instances
            ],
            "plexInstances": [
                {
                    "instanceName": instance.instance_name,
                    "url": instance.url,
                    "apiKey": instance.api_key,
                }
                for instance in plex_instances
            ],
            "gdrives": [
                {
                    "name": drive.drive_name,
                    "id": drive.drive_id,
                    "location": drive.drive_location,
                }
                for drive in gdrives
            ],
            "client_id": getattr(rclone, "client_id", ""),
            "rclone_token": getattr(rclone, "rclone_token", ""),
            "rclone_secret": getattr(rclone, "rclone_secret", ""),
            "sa_location": getattr(rclone, "service_account", ""),
        }
        return jsonify({"success": True, "settings": data})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@settings.route("/save-settings", methods=["POST"])
def save_settings():
    try:
        data = request.get_json()
        settings_data = {
            "log_level_unmatched_assets": data.get("logLevelUnmatchedAssets", ""),
            "log_level_poster_renamer": data.get("logLevelPosterRenamer", ""),
            "log_level_plex_uploaderr": data.get("logLevelPlexUploaderr", ""),
            "log_level_border_replacerr": data.get("logLevelBorderReplacerr", ""),
            "log_level_drive_sync": data.get("logLevelDriveSync", ""),
            "poster_renamer_schedule": data.get("posterRenamerSchedule", ""),
            "unmatched_assets_schedule": data.get("unmatchedAssetsSchedule", ""),
            "plex_uploaderr_schedule": data.get("plexUploaderrSchedule", ""),
            "drive_sync_schedule": data.get("driveSyncSchedule", ""),
            "target_path": data.get("targetPath", ""),
            "source_dirs": ",".join(data.get("sourceDirs", [])),
            "library_names": ",".join(data.get("libraryNames", [])),
            "instances": ",".join(data.get("instances", [])),
            "asset_folders": data.get("assetFolders", False),
            "clean_assets": data.get("cleanAssets", False),
            "unmatched_assets": data.get("unmatchedAssets", True),
            "replace_border": data.get("replaceBorder", False),
            "border_setting": data.get("borderSetting", ""),
            "custom_color": data.get("customColor", ""),
            "run_single_item": data.get("runSingleItem", False),
            "only_unmatched": data.get("onlyUnmatched", False),
            "upload_to_plex": data.get("uploadToPlex", False),
            "match_alt": data.get("matchAlt", False),
            "reapply_posters": data.get("reapplyPosters", False),
            "show_all_unmatched": data.get("showAllUnmatched", False),
            "disable_unmatched_collections": data.get(
                "disableUnmatchedCollections", False
            ),
        }

        models.Settings.query.delete()
        models.RadarrInstance.query.delete()
        models.SonarrInstance.query.delete()
        models.PlexInstance.query.delete()
        models.GDrives.query.delete()
        models.RCloneConf.query.delete()

        new_settings = models.Settings(**settings_data)
        db.session.add(new_settings)

        def add_instance(data_key, model):
            for instance_data in data.get(data_key, []):
                new_instance = model(
                    instance_name=instance_data.get("instanceName"),
                    url=instance_data.get("url"),
                    api_key=instance_data.get("apiKey"),
                )
                db.session.add(new_instance)

        for gdrive_data in data.get("gdriveData", []):
            new_drive = models.GDrives(
                drive_name=gdrive_data.get("name", ""),
                drive_id=gdrive_data.get("id", ""),
                drive_location=gdrive_data.get("location", ""),
            )
            db.session.add(new_drive)

        if "rcloneData" in data:
            rclone_data = data["rcloneData"]
            new_rclone_conf = models.RCloneConf(
                client_id=rclone_data.get("client_id", ""),
                rclone_token=rclone_data.get("rclone_token", ""),
                rclone_secret=rclone_data.get("rclone_secret", ""),
                service_account=rclone_data.get("sa_location", ""),
            )
            db.session.add(new_rclone_conf)

        add_instance("radarrInstances", models.RadarrInstance)
        add_instance("sonarrInstances", models.SonarrInstance)
        add_instance("plexInstances", models.PlexInstance)

        db.session.commit()

        trigger_reload_signal()

        return jsonify({"success": True, "message": "Settings saved successfully!"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


def trigger_reload_signal():
    from daps_webui import daps_logger

    socket_path = Settings.SOCKET_PATH.value
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(socket_path)
        client.sendall(b"reload")
        client.close()
        daps_logger.info("Sent reload signal to scheduler.")
    except Exception as e:
        daps_logger.error(f"Failed to send reload signal: {e}")


@settings.route("/test-connection", methods=["POST"])
def test_connection():
    data = request.get_json()

    url = data.get("url")
    api_key = data.get("apiKey")
    instance_type = data.get("instanceType")
    if instance_type in ["radarr", "sonarr"]:
        headers = {"X-Api-Key": api_key}
    elif instance_type == "plex":
        headers = {"X-Plex-Token": api_key}
    else:
        return jsonify({"success": False, "message": "Invalid instance type"}), 400

    response = None

    try:
        if instance_type == "radarr":
            response = requests.get(
                f"{url}/api/v3/system/status", headers=headers, timeout=5
            )
        elif instance_type == "sonarr":
            response = requests.get(
                f"{url}/api/v3/system/status", headers=headers, timeout=5
            )
        elif instance_type == "plex":
            response = requests.get(
                f"{url}/status/sessions", headers=headers, timeout=5
            )

        if response and response.status_code == 200:
            return jsonify({"success": True, "message": "Connection successful!"})
        else:
            return jsonify({"success": False, "message": "Failed to connect!"}), 400
    except requests.RequestException as e:
        return jsonify({"success": False, "message": str(e)}), 400
