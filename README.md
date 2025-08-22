# Deployer 2.0

Una plataforma completa de gestión y despliegue de proyectos construida con Flask y WebSockets para monitoreo en tiempo real.

## 🚀 Características Principales

- **Gestión de Proyectos**: Clona, gestiona y ejecuta proyectos Git desde un vault local
- **Monitoreo en Tiempo Real**: Logs en vivo con WebSockets y métricas del sistema
- **Interfaz Moderna**: Frontend React con actualizaciones en tiempo real
- **Gestión de Entornos**: Creación automática de entornos virtuales Python
- **API REST Completa**: Endpoints para todas las operaciones de proyectos
- **Almacenamiento JSON**: Sistema de persistencia ligero y confiable

## 📋 Requisitos

- Python 3.8+
- Git
- Node.js 16+ (para el frontend)

## ⚡ Instalación Rápida

### 1. Clonar y Configurar
```bash
git clone <repository-url>
cd Deployer-2.0

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar Variables de Entorno
```bash
# Opción 1: Configuración automática (recomendado)
python3 setup_env.py

# Opción 2: Configuración manual
cp .env.example .env
nano .env
```

### 3. Ejecutar Aplicación
```bash
python3 app.py
```

### 4. Acceder
Abrir navegador en: **http://127.0.0.1:8080**

## 🏗️ Arquitectura del Proyecto

```
deployer/
├── api/                    # Endpoints REST
│   ├── projects.py        # API de proyectos
│   └── system.py          # API del sistema
├── middleware/            # Middleware de Flask
│   └── rate_limiter.py    # Limitación de tasa
├── models/                # Modelos de datos
│   └── project_json.py    # Modelo de proyecto
├── services/              # Lógica de negocio
│   ├── log_service.py     # Servicio de logs
│   ├── process_service.py # Gestión de procesos
│   └── project_service_json.py # Servicio de proyectos
├── static/dist/           # Frontend compilado (React)
├── storage/               # Capa de persistencia
│   └── json_storage.py    # Almacenamiento JSON
├── utils/                 # Utilidades
│   ├── env_config.py      # Configuración de entorno
│   ├── security.py        # Utilidades de seguridad
│   └── validators.py      # Validadores
├── views/                 # Rutas web
│   └── main.py           # Rutas principales
└── websocket/            # WebSockets
    └── events.py         # Eventos en tiempo real
```

## 📚 API Reference

### Proyectos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/projects` | Obtener todos los proyectos |
| `POST` | `/api/projects` | Crear nuevo proyecto |
| `GET` | `/api/projects/{name}` | Obtener proyecto específico |
| `DELETE` | `/api/projects/{name}` | Eliminar proyecto |
| `POST` | `/api/projects/{name}/start` | Iniciar proyecto |
| `POST` | `/api/projects/{name}/stop` | Detener proyecto |
| `POST` | `/api/projects/{name}/venv` | Crear entorno virtual |
| `DELETE` | `/api/projects/{name}/venv` | Eliminar entorno virtual |
| `POST` | `/api/projects/{name}/install` | Instalar requirements |
| `GET` | `/api/projects/{name}/logs` | Obtener logs del proyecto |

### Sistema

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/health` | Estado de salud de la aplicación |

## ⚙️ Configuración

### Variables de Entorno Principales

| Variable | Descripción | Valor por Defecto |
|----------|-------------|-------------------|
| `VAULT_PATH` | Directorio para proyectos | `vault` |
| `HOST` | Host del servidor | `127.0.0.1` |
| `PORT` | Puerto del servidor | `8080` |
| `SECRET_KEY` | Clave secreta Flask | Auto-generada |
| `DEBUG` | Modo debug | `True` |
| `MAX_CONCURRENT_PROJECTS` | Máximo proyectos simultáneos | `10` |
| `LOG_RETENTION_HOURS` | Retención de logs (horas) | `24` |

### Configuración por Entorno

#### Desarrollo
```bash
FLASK_ENV=development
DEBUG=True
DISABLE_RATE_LIMITING=True
```

#### Producción
```bash
FLASK_ENV=production
DEBUG=False
SECRET_KEY=tu-clave-super-secreta
HOST=0.0.0.0
PORT=80
```

## 🔧 Uso

### Crear un Proyecto
```bash
# Via API
curl -X POST http://localhost:8080/api/projects \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/user/repo.git"}'

# Via interfaz web
# 1. Acceder a http://localhost:8080
# 2. Ir a la pestaña "Projects"
# 3. Hacer clic en "Add Project"
# 4. Introducir URL del repositorio
```

### Gestionar Proyectos
- **Iniciar proyecto**: `POST /api/projects/{name}/start`
- **Ver logs en tiempo real**: WebSocket connection automática
- **Crear entorno virtual**: `POST /api/projects/{name}/venv`
- **Instalar dependencias**: `POST /api/projects/{name}/install`

### Estructura del Vault
```
vault/
├── data/                  # Datos de configuración
├── proyecto1/             # Proyecto clonado
│   ├── .git/
│   ├── venv/             # Entorno virtual (si existe)
│   ├── requirements.txt
│   └── ...
└── proyecto2/
    └── ...
```

## 🐛 Solución de Problemas

### Problemas Comunes

1. **Proyectos no se cargan**
   - Verificar que el directorio `vault` existe
   - Comprobar permisos de lectura/escritura
   - Revisar logs en la consola

2. **Error de SECRET_KEY en producción**
   ```bash
   # Agregar al archivo .env
   SECRET_KEY=tu-clave-secreta-muy-larga-y-segura
   ```

3. **Proyectos no inician**
   - Verificar que `requirements.txt` existe
   - Comprobar que Python está disponible
   - Revisar logs del proyecto específico

4. **WebSockets no funcionan**
   - Verificar que el puerto no está bloqueado
   - Comprobar configuración de CORS
   - Revisar logs del navegador

### Logs y Debug

```bash
# Ver logs de la aplicación
tail -f deployer.log

# Modo debug completo
DEBUG=True python3 app.py

# Logs específicos de un proyecto
curl http://localhost:8080/api/projects/mi-proyecto/logs
```

## 🔄 Migración desde Versión Anterior

Si tienes una versión anterior con `config.py`:

1. **Migrar configuración**:
   ```bash
   python3 setup_env.py
   ```

2. **Verificar vault**:
   - Los proyectos existentes se detectarán automáticamente
   - No es necesario migrar datos

3. **Actualizar scripts**:
   - Cambiar referencias de `manage.py` por `app.py`
   - Actualizar rutas de API si es necesario

## 📈 Rendimiento

### Optimizaciones Implementadas

- **Caché de proyectos**: Los proyectos se cachean por 30 segundos
- **Lazy loading**: Git URLs se cargan solo cuando es necesario
- **Timeouts**: Comandos git tienen timeout de 5 segundos
- **Logs eficientes**: Los logs se cargan por separado, no en el listado principal

### Métricas de Rendimiento

- Carga inicial de proyectos: ~100-500ms (según número de proyectos)
- Actualización de estado: ~50-100ms
- WebSocket latencia: <50ms
- Memoria base: ~50-100MB

## 🤝 Contribuir

1. Fork el proyecto
2. Crear branch de feature (`git checkout -b feature/nueva-caracteristica`)
3. Commit cambios (`git commit -m 'Agregar nueva característica'`)
4. Push al branch (`git push origin feature/nueva-caracteristica`)
5. Abrir Pull Request

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Ver archivo `LICENSE` para más detalles.

## 🆘 Soporte

- **Issues**: [GitHub Issues](link-to-issues)
- **Documentación**: Este README y archivos en `/docs`
- **Logs**: Revisar `deployer.log` para debug detallado

---

**Versión**: 2.0  
**Última actualización**: Agosto 2024  
**Tecnologías**: Python 3.8+, Flask 2.3+, WebSockets, React