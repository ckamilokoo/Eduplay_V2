from bleak import BleakClient, BleakScanner
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Union
import asyncio
from fastapi.middleware.cors import CORSMiddleware

motor_characteristic_uuid = "00001565-1212-efde-1523-785feabcd123"
color_characteristic_uuid = "00001565-1212-efde-1523-785feabcd123"

class Command(BaseModel):
    type: str
    value: Union[int, str]

class CommandList(BaseModel):
    commands: List[Command]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*","http://localhost:5173"],  # Permitir todas las orígenes
    allow_credentials=True,
    allow_methods=["*","POST"],  # Permitir todos los métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permitir todas las cabeceras
)

clients = []  # Lista para almacenar los clientes conectados



async def scan_for_wedo():
    devices = await BleakScanner.discover()
    possible_wedo_devices = [
        device for device in devices
        if device.name is None or not any(apple_device in device.name for apple_device in ["iPhone", "iPad", "Apple Watch", "AirPods"])
    ]
    
    if possible_wedo_devices:
        # Seleccionar el dispositivo con la señal más fuerte (RSSI más alto)
        strongest_device = max(possible_wedo_devices, key=lambda device: device.rssi if device.rssi is not None else -100)
        print(f"Strongest device found: {strongest_device.address}, RSSI: {strongest_device.rssi}")
        return strongest_device.address
    else:
        print("No LEGO WeDo devices found.")
        return None

async def connect_to_wedo():
    device_address = await scan_for_wedo()  # Escanear el dispositivo antes de conectarse
    if not device_address:
        return None
    
    client = BleakClient(device_address)
    try:
        await client.connect()
        clients.append(client)  # Agregar el cliente a la lista de clientes conectados
        print(f"Connected to WeDo 2.0 at {device_address}")
        return client
    except Exception as e:
        print(f"Failed to connect: {e}")
        return None

async def disconnect_from_device(client):
    if client and client.is_connected:
        await client.disconnect()
        print(f"Disconnected from device at {client.address}")
        clients.remove(client)

# Definir la lista de colores
colors = {
    "off": b'\x00',
    "pink": b'\x01',
    "violet": b'\x02',
    "blue": b'\x03',
    "light_blue": b'\x04',
    "light_green": b'\x05',
    "dark_green": b'\x06',
    "yellow": b'\x07',
    "orange": b'\x08',
    "red": b'\x09',
    "white": b'\x0A'
}

def get_motor_command(speed):
    if speed < 0:
        speed_byte = 0x100 + speed  # Speed backward
    else:
        speed_byte = speed  # Speed forward
    
    command = bytearray([0x01, 0x01, 0x01, speed_byte])
    return command

async def run_motor(client, speed):
    motor_characteristic_uuid = "00001565-1212-efde-1523-785feabcd123"
    command = get_motor_command(speed)
    await client.write_gatt_char(motor_characteristic_uuid, command)

async def stop_motor(client):
    await run_motor(client, 0)  # Stop the motor

async def change_color(client, color_command):
    # Comando para cambiar el color del LED
    color_characteristic_uuid = "00001565-1212-efde-1523-785feabcd123"
    command = b"\x06\x04\x01" + color_command
    await client.write_gatt_char(color_characteristic_uuid, command)

async def main(client, commands_list):
    for i, command in enumerate(commands_list):
        if isinstance(command, int):  # Si el comando es un número, es una rotación
            if i > 0 and isinstance(commands_list[i-1], str):  # Detener el motor si el comando anterior fue un color
                await stop_motor(client)
                await asyncio.sleep(1)  # Pequeño retraso antes de cambiar la dirección
            
            speed = 33 if command > 0 else -33
            time_per_rotation = 3.5 / abs(3)  # Calcular el tiempo necesario
            total_time = time_per_rotation * abs(command)
            
            await run_motor(client, speed)
            await asyncio.sleep(total_time)
            await stop_motor(client)
        
        elif isinstance(command, str) and command in colors:  # Si el comando es un color
            if i > 0 and isinstance(commands_list[i-1], int):  # Detener el motor si el comando anterior fue una rotación
                await stop_motor(client)
                await asyncio.sleep(1)  # Pequeño retraso antes de cambiar el color

            await change_color(client, colors[command])
            print(f"Changed color to: {command}")
            await asyncio.sleep(2)  # Espera para ver el color antes de cambiar al siguiente comando

    await stop_motor(client)


@app.post("/connect")
async def connect():
    client = await connect_to_wedo()
    if client:
        return {"success": True, "message": "Connected successfully"}
    else:
        return {"success": False, "message": "No WeDo devices found or failed to connect"}


@app.post("/disconnect")
async def disconnect():
    await disconnect_all_devices()
    return {"success": True, "message": "Disconnected successfully"}

# Ruta GET para pruebas
@app.get("/test")
async def test():
    return {"message": "API is working!"}



@app.post("/send_commands")
async def send_commands(commands: CommandList):
    if not clients:
        raise HTTPException(status_code=400, detail="No devices connected")

    # Transformar los comandos en la lista que la función `main` espera
    commands_list = []
    for cmd in commands.commands:
        if cmd.type == "motor":
            commands_list.append(cmd.value)
        elif cmd.type == "color":
            commands_list.append(cmd.value)

    # Iterar sobre todos los clientes conectados y enviarles los comandos
    for client in clients:
        await main(client, commands_list)

    return {"message": "Commands sent to devices"}



async def disconnect_all_devices():
    for client in clients:
        await disconnect_from_device(client)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

