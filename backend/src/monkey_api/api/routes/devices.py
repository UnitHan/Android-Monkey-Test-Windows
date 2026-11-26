"""Devices, wireless connection, installed packages."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from monkey_api.api.container import Container, get_container
from monkey_api.api.errors import problem_responses
from monkey_api.api.schemas import AcceptedOut, ConnectIn, ConnectOut, DeviceList, PackageList, PairIn, PairOut, TcpipIn
from monkey_api.domain.icon import AppIcon
from monkey_api.domain.models import PACKAGE_PATTERN, DeviceInfo, PackageVersion

router = APIRouter(prefix="/devices", tags=["devices"])

_ADB_ERRORS = problem_responses(404, 422, 502, 503, 504)
Serial = Path(min_length=1, max_length=128)
PackageName = Path(pattern=PACKAGE_PATTERN)


@router.get("", response_model=DeviceList, responses=_ADB_ERRORS)
async def list_devices(c: Container = Depends(get_container)) -> DeviceList:
    return DeviceList(items=await c.ops.list_devices())


@router.post("/connect", response_model=ConnectOut, responses=_ADB_ERRORS)
async def connect(body: ConnectIn, c: Container = Depends(get_container)) -> ConnectOut:
    return ConnectOut(serial=await c.ops.connect(body.host, body.port))


@router.post("/pair", response_model=PairOut, responses=_ADB_ERRORS)
async def pair(body: PairIn, c: Container = Depends(get_container)) -> PairOut:
    return PairOut(message=await c.ops.pair(body.host, body.port, body.code))


@router.get("/{serial}", response_model=DeviceInfo, responses=_ADB_ERRORS)
async def device_info(serial: str = Serial, c: Container = Depends(get_container)) -> DeviceInfo:
    return await c.ops.device_info(serial)


@router.post("/{serial}/disconnect", status_code=204, responses=_ADB_ERRORS)
async def disconnect(serial: str = Serial, c: Container = Depends(get_container)) -> None:
    await c.ops.disconnect(serial)


@router.post("/{serial}/tcpip", status_code=202, response_model=AcceptedOut, responses=_ADB_ERRORS)
async def enable_tcpip(body: TcpipIn, serial: str = Serial, c: Container = Depends(get_container)) -> AcceptedOut:
    """Switch a USB device to wireless debugging on `port` (then POST /devices/connect)."""
    await c.ops.require_device(serial)
    await c.ops.enable_tcpip(serial, body.port)
    return AcceptedOut(message=f"tcpip enabled on {body.port}")


@router.post("/{serial}/reboot", status_code=202, response_model=AcceptedOut, responses=_ADB_ERRORS)
async def reboot(serial: str = Serial, c: Container = Depends(get_container)) -> AcceptedOut:
    await c.ops.require_device(serial)
    await c.ops.reboot(serial)
    return AcceptedOut(message="reboot requested")


@router.get("/{serial}/packages", response_model=PackageList, responses=_ADB_ERRORS)
async def list_packages(
    serial: str = Serial,
    query: str | None = None,
    include_system: bool = False,
    third_party: bool = False,
    refresh: bool = False,
    c: Container = Depends(get_container),
) -> PackageList:
    await c.ops.require_device(serial)
    items = await c.packages.list(
        serial, query=query, include_system=include_system, third_party=third_party, refresh=refresh
    )
    return PackageList(items=items, total=len(items))


@router.get("/{serial}/packages/{package}", response_model=PackageVersion, responses=_ADB_ERRORS)
async def package_version(
    serial: str = Serial, package: str = PackageName, c: Container = Depends(get_container)
) -> PackageVersion:
    return await c.packages.version(serial, package)


@router.post("/{serial}/packages/{package}/launch", status_code=204, responses=_ADB_ERRORS)
async def launch_package(
    serial: str = Serial, package: str = PackageName, c: Container = Depends(get_container)
) -> None:
    await c.ops.require_device(serial)
    await c.ops.launch(serial, package)


@router.get("/{serial}/packages/{package}/icon", response_model=AppIcon, responses=_ADB_ERRORS)
async def package_icon(
    serial: str = Serial, package: str = PackageName, c: Container = Depends(get_container)
) -> AppIcon:
    return await c.icons.get(serial, package)
