import base64
import datetime
import json

from bottle import Bottle, HTTPResponse, abort, redirect, request
from jumpscale.core.base import StoredFactory
from jumpscale.loader import j
from jumpscale.packages.auth.bottle.auth import (
    authenticated,
    get_user_info,
    login_required,
    package_authorized,
)
from jumpscale.sals.zos.billing import InsufficientFunds
import nacl
import requests

from jumpscale.packages.jukebox.bottle.models import UserEntry
from jumpscale.sals.jukebox import utils

app = Bottle()

THREEFOLD_LOGIN_URL = "https://login.threefold.me/api"

IDENTITY_PREFIX = "jukebox"
JUKEBOX_AUTO_EXTEND_KEY = "jukebox:auto_extend"


@app.route("/api/status", method="GET")
@login_required
def is_running():
    return HTTPResponse(
        j.data.serializers.json.dumps({"running": True}), status=200, headers={"Content-Type": "application/json"}
    )


@app.route("/api/admins/list", method="GET")
@package_authorized("jukebox")
def list_all_admins() -> str:
    threebot = j.servers.threebot.get("default")
    package = threebot.packages.get("jukebox")
    admins = list(set(package.admins))
    return j.data.serializers.json.dumps({"data": admins})


@app.route("/api/admins/add", method="POST")
@package_authorized("jukebox")
def add_admin() -> str:
    data = j.data.serializers.json.loads(request.body.read())
    name = data.get("name")
    threebot = j.servers.threebot.get("default")
    package = threebot.packages.get("jukebox")
    if not name:
        raise j.exceptions.Value(f"Admin name shouldn't be empty")
    if name in package.admins:
        raise j.exceptions.Value(f"Admin {name} already exists")
    package.admins.append(name)
    threebot.packages.save()


@app.route("/api/admins/remove", method="POST")
@package_authorized("jukebox")
def remove_admin() -> str:
    data = j.data.serializers.json.loads(request.body.read())
    name = data.get("name")
    threebot = j.servers.threebot.get("default")
    package = threebot.packages.get("jukebox")
    if not name:
        raise j.exceptions.Value(f"Admin name shouldn't be empty")
    if name not in package.admins:
        raise j.exceptions.Value(f"Admin {name} does not exist")
    if len(package.admins) == 1:
        raise j.exceptions.Value(f"Jukebox should have at least one admin")
    j.logger.info(f"Removing admin {name}")
    package.admins.remove(name)
    threebot.packages.save()


def create_intermediate_identity(tname, email, explorer_url):

    prefixed_tname = f"{IDENTITY_PREFIX}_{j.data.text.removesuffix(tname, '.3bot')}"
    suffixed_email = email.replace("@", "_jukebox@")
    identity = j.core.identity.find(prefixed_tname)
    if not identity:
        identity = j.core.identity.new(
            name=prefixed_tname, tname=prefixed_tname, email=suffixed_email, explorer_url=explorer_url
        )
        identity.register()
        identity.save()


@app.route("/api/accept", method="GET")
@login_required
def accept():
    user_factory = StoredFactory(UserEntry)

    user_info = j.data.serializers.json.loads(get_user_info())
    tname = user_info["username"]
    explorer_url = j.core.identity.me.explorer.url

    if "testnet" in explorer_url:
        explorer_name = "testnet"
    elif "devnet" in explorer_url:
        explorer_name = "devnet"
    elif "explorer.grid.tf" in explorer_url:
        explorer_name = "mainnet"
    else:
        return HTTPResponse(
            j.data.serializers.json.dumps({"error": f"explorer {explorer_url} is not supported"}),
            status=500,
            headers={"Content-Type": "application/json"},
        )
    user_entry_name = f"{IDENTITY_PREFIX}_{tname.replace('.3bot', '')}"
    user_entry = user_factory.get(user_entry_name)
    if user_entry.has_agreed:
        return HTTPResponse(
            j.data.serializers.json.dumps({"allowed": True}), status=200, headers={"Content-Type": "application/json"}
        )
    else:
        user_entry.has_agreed = True
        user_entry.explorer_url = explorer_url
        user_entry.tname = tname
        user_entry.save()
        utils.get_or_create_user_wallet(f"jukebox_{j.data.text.removesuffix(tname, '.3bot')}")
        create_intermediate_identity(tname=tname, email=user_info["email"], explorer_url=explorer_url)
        return HTTPResponse(
            j.data.serializers.json.dumps({"allowed": True}), status=201, headers={"Content-Type": "application/json"}
        )


@app.route("/api/allowed", method="GET")
@authenticated
def allowed():
    user_factory = StoredFactory(UserEntry)
    user_info = j.data.serializers.json.loads(get_user_info())
    tname = user_info["username"]
    explorer_url = j.core.identity.me.explorer.url
    instances = user_factory.list_all()
    for name in instances:
        user_entry = user_factory.get(name)
        utils.get_or_create_user_wallet(f"jukebox_{j.data.text.removesuffix(tname, '.3bot')}")
        if user_entry.tname == tname and user_entry.explorer_url == explorer_url and user_entry.has_agreed:
            create_intermediate_identity(
                tname=tname, email=user_info["email"], explorer_url=explorer_url
            )  # check if not created, then add
            return j.data.serializers.json.dumps({"allowed": True})
    return j.data.serializers.json.dumps({"allowed": False})


@app.route("/api/deployments/<solution_type>", method="GET")
@package_authorized("jukebox")
def list_deployments(solution_type: str) -> str:
    user_info = j.data.serializers.json.loads(get_user_info())
    tname = user_info["username"]
    prefixed_tname = f"{IDENTITY_PREFIX}_{tname.replace('.3bot', '')}"
    deployments = j.sals.jukebox.list_deployments(prefixed_tname, solution_type.lower())
    deployments = [deployment.to_dict() for deployment in deployments]

    return j.data.serializers.json.dumps({"data": deployments})


@app.route("/api/deployments/cancel", method="POST")
@package_authorized("jukebox")
def cancel_deployment() -> str:
    user_info = j.data.serializers.json.loads(get_user_info())
    tname = user_info["username"]
    prefixed_tname = f"{IDENTITY_PREFIX}_{tname.replace('.3bot', '')}"

    data = j.data.serializers.json.loads(request.body.read())
    deployment_name = data.get("name")
    solution_type = data.get("solution_type", "").lower()

    deployment = j.sals.jukebox.find(
        identity_name=prefixed_tname, deployment_name=deployment_name, solution_type=solution_type
    )
    j.sals.jukebox.delete(deployment.instance_name)
    return j.data.serializers.json.dumps({"data": {}})


@app.route("/api/node/cancel", method="POST")
@package_authorized("jukebox")
def cancel_node() -> str:
    user_info = j.data.serializers.json.loads(get_user_info())
    tname = user_info["username"]
    prefixed_tname = f"{IDENTITY_PREFIX}_{tname.replace('.3bot', '')}"

    data = j.data.serializers.json.loads(request.body.read())
    deployment_name = data.get("name")
    wid = data.get("wid")
    solution_type = data.get("solution_type", "").lower()

    deployment = j.sals.jukebox.find(
        identity_name=prefixed_tname, deployment_name=deployment_name, solution_type=solution_type
    )
    deployment.delete_node(wid)
    return j.data.serializers.json.dumps({"data": {}})


@app.route("/api/deployments/switch_auto_extend", method="POST")
@package_authorized("jukebox")
def switch_auto_extend() -> str:
    user_info = j.data.serializers.json.loads(get_user_info())
    tname = user_info["username"]
    prefixed_tname = f"{IDENTITY_PREFIX}_{tname.replace('.3bot', '')}"

    data = j.data.serializers.json.loads(request.body.read())
    deployment_name = data.get("name")
    new_state = data.get("new_state", False)
    solution_type = data.get("solution_type", "").lower()

    deployment = j.sals.jukebox.find(
        identity_name=prefixed_tname, deployment_name=deployment_name, solution_type=solution_type
    )
    deployment.auto_extend = new_state
    deployment.save()


@app.route("/api/deployments/extend", method="POST")
@package_authorized("jukebox")
def extend_deployment() -> str:
    user_info = j.data.serializers.json.loads(get_user_info())
    tname = user_info["username"]
    prefixed_tname = f"{IDENTITY_PREFIX}_{tname.replace('.3bot', '')}"

    data = j.data.serializers.json.loads(request.body.read())
    deployment_name = data.get("name")
    solution_type = data.get("solution_type", "").lower()

    deployment = j.sals.jukebox.find(
        identity_name=prefixed_tname, deployment_name=deployment_name, solution_type=solution_type
    )
    try:
        deployment.extend()
    except InsufficientFunds as e:
        j.logger.exception("Failed to extend deployment due to insufficient funds in the wallet", exception=e)
        return HTTPResponse(
            "Failed to extend deployment due to insufficient funds in the wallet. To fund it, click on FUND WALLET",
            status=500,
            headers={"Content-Type": "application/json"},
        )

    except Exception as e:
        j.logger.exception("Failed to extend deployment", exception=e)
        return HTTPResponse("Failed to extend deployment", status=500, headers={"Content-Type": "application/json"})


@app.route("/api/wallet", method="GET")
@package_authorized("jukebox")
def get_wallet():
    user_info = j.data.serializers.json.loads(get_user_info())
    tname = user_info["username"]
    prefixed_tname = f"{IDENTITY_PREFIX}_{tname.replace('.3bot', '')}"

    data = utils.get_wallet_funding_info(prefixed_tname)
    if not data:
        return HTTPResponse(
            j.data.serializers.json.dumps({"wallet": False}), status=404, headers={"Content-Type": "application/json"}
        )

    return j.data.serializers.json.dumps({"data": data})


@app.route("/api/deployments/secret", method="POST")
@package_authorized("jukebox")
def get_secret():
    user_info = j.data.serializers.json.loads(get_user_info())
    tname = user_info["username"]
    prefixed_tname = f"{IDENTITY_PREFIX}_{tname.replace('.3bot', '')}"

    data = j.data.serializers.json.loads(request.body.read())
    deployment_name = data.get("name")
    solution_type = data.get("solution_type", "").lower()
    deployment = j.sals.jukebox.find(
        identity_name=prefixed_tname, deployment_name=deployment_name, solution_type=solution_type
    )
    try:
        secret = utils.decrypt_secret_env(deployment)
    except Exception as e:
        return HTTPResponse("Failed to get deployment secret", status=404, headers={"Content-Type": "application/json"})

    return j.data.serializers.json.dumps({"data": secret})
