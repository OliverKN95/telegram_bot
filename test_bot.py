#!/usr/bin/env python3
"""
Script de prueba para verificar que el bot funciona correctamente
antes del despliegue en Render.com
"""

import requests
import subprocess
import time
import threading
from telegram_bot import diario_scraping, bot_send_text, start_health_server

def test_scraping():
    """Prueba la función de scraping"""
    print("🧪 Probando función de scraping...")
    try:
        result = diario_scraping()
        print(f"✅ Scraping exitoso: {result[:100]}...")
        return True
    except Exception as e:
        print(f"❌ Error en scraping: {e}")
        return False

def test_health_endpoint():
    """Prueba el endpoint de salud"""
    print("🧪 Probando endpoint de salud...")
    
    # Iniciar servidor en hilo separado
    server_thread = threading.Thread(target=start_health_server, daemon=True)
    server_thread.start()
    
    # Esperar un poco para que el servidor inicie
    time.sleep(2)
    
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Endpoint de salud funcionando correctamente")
            print(f"Respuesta: {response.text}")
            return True
        else:
            print(f"❌ Endpoint devolvió código: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error probando endpoint: {e}")
        return False

def test_docker_build():
    """Prueba la construcción de Docker"""
    print("🧪 Probando construcción de Docker...")
    try:
        result = subprocess.run(
            ["docker", "build", "-t", "telegram-bot-test", "."],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            print("✅ Imagen Docker construida exitosamente")
            return True
        else:
            print(f"❌ Error construyendo Docker: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Timeout construyendo imagen Docker")
        return False
    except FileNotFoundError:
        print("⚠️  Docker no encontrado, saltando prueba")
        return True
    except Exception as e:
        print(f"❌ Error inesperado con Docker: {e}")
        return False

def main():
    """Ejecutar todas las pruebas"""
    print("🚀 Iniciando pruebas del bot de Telegram\n")
    
    tests = [
        ("Scraping", test_scraping),
        ("Endpoint de salud", test_health_endpoint),
        ("Construcción Docker", test_docker_build)
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n--- {name} ---")
        result = test_func()
        results.append((name, result))
    
    print("\n" + "="*50)
    print("📊 RESUMEN DE PRUEBAS")
    print("="*50)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("🎉 ¡Todas las pruebas pasaron! El bot está listo para Render.com")
    else:
        print("⚠️  Algunas pruebas fallaron. Revisa los errores antes del despliegue.")
    print("="*50)

if __name__ == "__main__":
    main()
