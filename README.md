# 🚀 Deployer 1.0 - Gestor de Proyectos Python

Un sistema web moderno para gestionar y ejecutar proyectos Python desde repositorios de GitHub con una interfaz web intuitiva y logs en tiempo real. **Ahora con arquitectura Flask profesional y seguridad mejorada.**

## ✨ Características

- 🚀 **Clonado automático** de repositorios de GitHub
- 📦 **Gestión automática** de entornos virtuales
- 📋 **Instalación automática** de dependencias (requirements.txt)
- 🏃‍♂️ **Ejecución de proyectos** con logs en tiempo real
- 🔄 **Actualización de repositorios** Git
- 📊 **Análisis de estructura** de archivos con detección de errores
- 🛡️ **Validación de seguridad** y protección contra path traversal
- 🎨 **Interfaz web moderna** y responsiva
- ⚡ **Polling HTTP** para actualizaciones automáticas (compatible con Grok)
- 🏗️ **Arquitectura Flask profesional** con separación de responsabilidades

## 📋 Requisitos

- Python 3.7+
- Git instalado en el sistema
- Acceso a repositorios de GitHub

## 🔧 Instalación

1. **Clonar o crear el proyecto**:
```bash
cd "/Users/tu-usuario/Desktop"
# Los archivos ya están en "Deployer 1.0/"
```

2. **Instalar dependencias**:
```bash
cd "Deployer 1.0"
pip3 install -r requirements.txt
```

3. **Crear carpeta vault** (se crea automáticamente al ejecutar):
```bash
sudo mkdir -p /vault
sudo chown $(whoami) /vault
```

## 🚀 Uso

### Iniciar el Deployer

**Modo desarrollo (recomendado para pruebas):**
```bash
FLASK_ENV=development python3 app.py
```

**Modo producción:**
```bash
export FLASK_ENV=production
export SECRET_KEY=tu_clave_secreta_muy_segura
python3 app.py
```

**Usando el nuevo punto de entrada:**
```bash
python3 run.py
```

El servidor estará disponible en: `http://127.0.0.1:5000`

## ⚙️ Configuración

### Variables de entorno

- `FLASK_ENV`: Entorno (`development`, `production`, `testing`)
- `SECRET_KEY`: Clave secreta (obligatoria en producción)
- `VAULT_PATH`: Directorio de proyectos (default: `./vault`)
- `MAX_CONCURRENT_PROJECTS`: Máximo de proyectos simultáneos (default: 10)
- `HOST`: Dirección IP del servidor (default: `127.0.0.1`)
- `PORT`: Puerto del servidor (default: `5000`)
- `LOG_LEVEL`: Nivel de logging (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `CORS_ORIGINS`: Orígenes permitidos para CORS
- `POLLING_INTERVAL`: Intervalo de polling en segundos (default: 3)

### Configuración por defecto

```python
VAULT_PATH = './vault'
MAX_CONCURRENT_PROJECTS = 10
PROCESS_TIMEOUT = 300  # segundos
LOG_RETENTION_HOURS = 24
MAX_LOG_ENTRIES = 500
POLLING_INTERVAL = 3  # segundos
```

### Estructura de Proyectos

Cada proyecto en `/vault` debe tener:
- Un archivo `__init__.py` en la raíz para poder ejecutarse
- Opcionalmente ser un repositorio Git para actualizaciones

Ejemplo de estructura:
```
/vault/
├── mi-proyecto/
│   ├── __init__.py          # Punto de entrada
│   ├── main.py
│   ├── requirements.txt
│   └── .git/
└── otro-proyecto/
    ├── __init__.py
    └── src/
```

### Funcionalidades Web

1. **Añadir Proyecto**:
   - Introduce la URL del repositorio GitHub
   - Opcionalmente especifica un nombre personalizado
   - El proyecto se clona automáticamente en `/vault`

2. **Ejecutar Proyecto**:
   - Click en "▶ Ejecutar" para iniciar el proyecto
   - Solo funciona si existe `__init__.py`
   - Se ejecuta con `python3 __init__.py`

3. **Ver Logs**:
   - Click en "📋 Ver Logs" para ver la salida en tiempo real
   - Los logs se actualizan automáticamente via WebSockets

4. **Actualizar Proyecto**:
   - Click en "🔄 Pull" para actualizar desde GitHub
   - Solo disponible para repositorios Git

5. **Eliminar Proyecto**:
   - Click en "🗑 Eliminar" para borrar completamente
   - No disponible mientras el proyecto esté ejecutándose

## 🔒 Seguridad

- ✅ **Validación de URLs** de GitHub para prevenir inyección
- ✅ **Sanitización de nombres** de proyecto con caracteres seguros
- ✅ **Protección path traversal** para evitar acceso a directorios no autorizados
- ✅ **Variables de entorno** seguras con claves generadas automáticamente
- ✅ **CORS configurado** para orígenes específicos
- ✅ **Gestión segura de procesos** con timeouts y cleanup automático
- ✅ **Logs seguros** que no exponen información sensible
- ✅ **Singleton services** para control centralizado de recursos

## 🐛 Troubleshooting

### Proyecto no se ejecuta
- Verifica que existe `__init__.py` en la raíz del proyecto
- Revisa que el archivo tiene permisos de ejecución
- Comprueba los logs para ver errores específicos

### Error de permisos en /vault
```bash
sudo chown -R $(whoami) /vault
```

### Puerto 5000 ocupado
Modifica el puerto en `app.py`:
```python
socketio.run(app, host='0.0.0.0', port=5001, debug=True)
```

## 🏗️ Arquitectura

El proyecto sigue una arquitectura estándar de Flask con separación de responsabilidades:

```
Deployer 1.0/
├── app.py                   # Punto de entrada compatible
├── run.py                   # Punto de entrada moderno
├── config.py                # Configuración por entornos
├── requirements.txt         # Dependencias Python
├── deployer/                # Paquete principal
│   ├── __init__.py         # Factory de aplicación Flask
│   ├── api/                # Endpoints de API REST
│   │   ├── projects.py     # API de proyectos
│   │   └── system.py       # API del sistema
│   ├── models/             # Modelos de datos
│   │   └── project.py      # Modelo de proyecto y logs
│   ├── services/           # Lógica de negocio
│   │   ├── project_service.py   # Gestión de proyectos
│   │   ├── process_service.py   # Gestión de procesos
│   │   └── socket_service.py    # WebSocket/SocketIO
│   ├── utils/              # Utilidades
│   │   ├── security.py     # Seguridad y validación
│   │   └── validators.py   # Validadores de entrada
│   ├── views/              # Vistas web
│   │   └── main.py         # Rutas principales
│   └── templates/          # Plantillas HTML
│       ├── index.html      # Interfaz principal
│       └── errors/         # Páginas de error
└── vault/                  # Proyectos gestionados
```

## 🔄 API REST

### Proyectos (`/api/projects/`)

- `GET /` - Listar todos los proyectos
- `POST /` - Crear proyecto desde GitHub
- `GET /<name>` - Obtener proyecto específico
- `DELETE /<name>` - Eliminar proyecto
- `POST /<name>/update` - Actualizar desde Git
- `POST /<name>/start` - Ejecutar proyecto
- `POST /<name>/stop` - Detener proyecto
- `GET /<name>/logs` - Obtener logs
- `GET /<name>/files` - Analizar estructura de archivos
- `POST /<name>/venv` - Crear entorno virtual
- `DELETE /<name>/venv` - Eliminar entorno virtual
- `POST /<name>/install` - Instalar requirements.txt

### Sistema (`/api/system/`)

- `GET /stats` - Estadísticas del sistema
- `GET /running` - Proyectos en ejecución
- `POST /cleanup` - Limpiar procesos terminados

## 📡 Sistema de Polling HTTP

La aplicación utiliza **polling HTTP** en lugar de WebSockets para ser compatible con tunnels como **Grok**:

- **Intervalo configurable**: Por defecto cada 3 segundos
- **Actualizaciones automáticas**: Lista de proyectos y logs
- **Eficiente**: Solo actualiza la UI cuando hay cambios
- **Compatible**: Funciona con cualquier proxy/tunnel HTTP
- **Sin dependencias**: No requiere librerías de WebSocket

### Configuración del Polling

```bash
export POLLING_INTERVAL=5  # Cambiar a 5 segundos
```

## 💡 Tips

- Los logs se limitan a 1000 entradas por proyecto para evitar uso excesivo de memoria
- Los procesos se guardan en `running_processes.json` para persistir entre reinicios
- Usa Ctrl+C para terminar el deployer de forma segura
- El sistema auto-refresca la lista de proyectos cada 30 segundos

## 🤝 Contribuir

1. Haz fork del proyecto
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request# Deployer-2.0
# Deployer-2.0
# Deployer-2.0
