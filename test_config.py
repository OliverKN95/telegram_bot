#!/usr/bin/env python3
"""
Script de prueba para verificar la configuración del archivo .env
"""

import os
from dotenv import load_dotenv

def test_env_config():
    """Prueba la configuración de variables de entorno"""
    print("=== Test de Configuración de Variables de Entorno ===\n")
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Variables requeridas
    required_vars = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID"
    ]
    
    # Variables opcionales con valores por defecto
    optional_vars = {
        "PORT": "8000",
        "SEARCH_TEXT": "koyoc novelo",
        "BASE_URL": "https://www.yucatan.gob.mx",
        "DIARIO_URL_PATH": "/gobierno/diario_oficial.php",
        "TIMEZONE": "America/Merida",
        "SCHEDULE_HOUR_1": "7",
        "SCHEDULE_MINUTE_1": "30",
        "SCHEDULE_HOUR_2": "12",
        "SCHEDULE_MINUTE_2": "0"
    }
    
    print("📋 Variables requeridas:")
    all_required_present = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Ocultar token para seguridad
            if "TOKEN" in var:
                display_value = value[:10] + "..." if len(value) > 10 else "***"
            else:
                display_value = value
            print(f"  ✅ {var}: {display_value}")
        else:
            print(f"  ❌ {var}: NO CONFIGURADA")
            all_required_present = False
    
    print("\n📋 Variables opcionales:")
    for var, default in optional_vars.items():
        value = os.getenv(var, default)
        print(f"  ✅ {var}: {value}")
    
    print(f"\n{'='*50}")
    if all_required_present:
        print("✅ Configuración completa - El bot está listo para ejecutarse")
    else:
        print("❌ Faltan variables requeridas - Revisa tu archivo .env")
        print("\nPara configurar:")
        print("1. Copia .env.example a .env")
        print("2. Edita .env con tus valores")
        
    print(f"{'='*50}")

def test_timezone():
    """Prueba la configuración de zona horaria"""
    print("\n🌍 Test de Zona Horaria:")
    try:
        import pytz
        from datetime import datetime
        
        timezone = os.getenv("TIMEZONE", "America/Merida")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        
        print(f"  ✅ Zona horaria: {timezone}")
        print(f"  ✅ Hora actual: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    except Exception as e:
        print(f"  ❌ Error con zona horaria: {e}")

if __name__ == "__main__":
    test_env_config()
    test_timezone()
