# Deployer 2.0

A comprehensive project management and monitoring platform built with Flask.

## Features

- **Project Management**: Deploy and manage Git repositories and local projects
- **Real-time Monitoring**: System and project metrics with live dashboard
- **Health Checks**: Automated HTTP endpoint monitoring and process health checks
- **Alerting System**: Configurable alerts with email/webhook/Slack notifications
- **User Authentication**: Role-based access control with audit logging
- **Interactive Dashboard**: Real-time charts and metrics visualization

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Application

```bash
# Activate virtual environment
source venv/bin/activate

# Start the application
python3 app.py
```

### 3. Access the Application

Open your browser and go to: **http://127.0.0.1:8080**

**Default admin credentials:**
- Username: `admin`
- Password: `admin123`

## Dashboard Features

### Projects Tab
- View and manage all projects
- Start/stop project processes
- Real-time logs with configurable polling
- Project settings and environment management

### Metrics Tab
- System performance overview (CPU, Memory, Disk)
- Project-specific metrics and health scores
- Interactive charts with time range selection
- Health status monitoring
- Active alerts and notification history

## API Endpoints

### Projects
- `GET /api/projects` - List all projects
- `POST /api/projects` - Create new project
- `GET /api/projects/{name}` - Get project details
- `POST /api/projects/{name}/start` - Start project
- `POST /api/projects/{name}/stop` - Stop project

### Metrics
- `GET /api/metrics/system` - System metrics
- `GET /api/metrics/projects` - All project metrics  
- `GET /api/metrics/project/{name}` - Specific project metrics
- `GET /api/metrics/health` - Health check status
- `GET /api/metrics/alerts` - Active alerts
- `GET /api/metrics/export/prometheus` - Prometheus export

## Configuration

The application uses environment variables for configuration:

```bash
export HOST=127.0.0.1
export PORT=8080
export FLASK_ENV=development
export DATABASE_URL=sqlite:///deployer.db
export VAULT_PATH=./vault
```

## Architecture

```
deployer/
├── api/           # REST API endpoints
├── auth/          # Authentication and authorization
├── database/      # Database models and migrations
├── middleware/    # Request/response middleware
├── monitoring/    # Metrics, alerts, and health checks
├── services/      # Business logic services
├── static/        # CSS, JavaScript, and assets
├── templates/     # HTML templates
├── utils/         # Utility functions
└── views/         # Web interface routes
```

## Development

The application uses:
- **Flask** for the web framework
- **SQLAlchemy** for database ORM
- **SQLite** for data storage
- **Chart.js** for metrics visualization
- **psutil** for system metrics collection

## Monitoring Features

- **Real-time metrics collection** every 30 seconds
- **Automatic data retention** (configurable, default 30 days)
- **HTTP health checks** for web applications
- **Process monitoring** for all managed projects
- **Configurable alerting** with multiple notification channels
- **Prometheus export** for external monitoring systems