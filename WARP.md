# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

MES Parafina App is a Manufacturing Execution System for managing paraffin wax production and purification processes. It's built with Flask/Python backend, MySQL database, and includes real-time monitoring with Socket.IO, background processing with Celery/Redis, and a React frontend.

## Development Commands

### Environment Setup
```powershell
# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies (for frontend components)
npm install

# Set up environment variables
# Copy .flaskenv.example to .flaskenv and configure
```

### Database Operations
```powershell
# Initialize/upgrade database schema
alembic upgrade head

# Create new migration after model changes
alembic revision --autogenerate -m "Description of changes"

# Downgrade database (if needed)
alembic downgrade -1
```

### Development Server
```powershell
# Run Flask development server with Socket.IO
python run.py

# Run Celery worker for background tasks
celery -A celery_app.celery worker -B -E -l info --scheduler celery_sqlalchemy_scheduler.schedulers.DatabaseScheduler --concurrency=2

# Run Flower for Celery monitoring
celery -A celery_app.celery flower --port=5555 --broker=redis://localhost:6379/0 --persistent=true
```

### Docker Development
```powershell
# Build and run with Docker Compose
docker-compose up --build

# Run specific service
docker-compose up web
docker-compose up celery-worker
```

### Testing
```powershell
# Run all tests
pytest

# Run specific test file
pytest test_apollo_service.py
pytest test_batch_management.py
pytest test_pathfinder_service.py

# Run tests with coverage
pytest --cov=app

# Run integration tests
pytest e_2_e_tests.py
```

### Database Management
```powershell
# Connect to MySQL database
mysql -h localhost -u root -p mes_parafina_db

# Backup database
mysqldump -h localhost -u root -p mes_parafina_db > backup.sql

# Restore database
mysql -h localhost -u root -p mes_parafina_db < backup.sql
```

### Configuration Management
```powershell
# Show current configuration
python show-config.ps1

# Run migration script
python migrate.ps1
```

## Architecture Overview

### Core Domain Models

**Primary Entities:**
- `Batches` - Immutable raw material batches with traceability (source: Apollo, cistern, etc.)
- `TankMixes` - Dynamic tank contents that evolve through production processes
- `Sprzet` - Equipment (reactors, filters, tanks, valves) with real-time sensor data
- `Segmenty`/`Zawory` - Pipeline topology for PathFinder routing system

**Process Management:**
- `OperacjeLog` - Audit trail for all production operations
- `AuditTrail` - System-level change tracking
- `ApolloSesje` - Apollo melter session management

### Service Architecture

**Core Services:**
1. **BatchManagementService** (`app/batch_management_service.py`)
   - Manages raw material batches and tank mixing operations
   - Handles proportional transfers and composition calculations
   - Provides automatic balance correction with audit trails

2. **PathFinder** (`app/pathfinder_service.py`)
   - NetworkX-based routing through plant pipeline topology
   - Dynamic path calculation based on valve states
   - Resource management for pipeline operations

3. **WorkflowService** (`app/workflow_service.py`)
   - Business process orchestration (heating, bleaching, filtration)
   - State machine for mix lifecycle management
   - Quality assessment workflows

4. **ApolloService** (`app/apollo_service.py`)
   - Integration with Apollo melter systems
   - Session tracking and material transfer validation

5. **HeatingService** (`app/heating_service.py`)
   - Temperature control and monitoring
   - Predictive heating models and optimization

### Production Process States

**TankMix Process Status Flow:**
- `SUROWY` → `PODGRZEWANY` → `DOBIELONY_OCZEKUJE` → `FILTRACJA_PLACEK_KOŁO` → `FILTRACJA_PRZELEW` → `FILTRACJA_KOŁO` → `OCZEKUJE_NA_OCENE` → `ZATWIERDZONA`/`DO_PONOWNEJ_FILTRACJI`

**Key Business Rules:**
- Bleaching operations require minimum 110°C temperature
- Filter contamination tracking with automatic virtual batch creation
- Blow-back operations marked with `is_wydmuch_mix` flag
- Proportional mixing calculations based on batch weights

### Real-time Architecture

**Socket.IO Integration:**
- Real-time equipment status updates
- Process notifications and alerts
- Dashboard live data streaming

**Celery Background Processing:**
- Temperature monitoring and control
- Sensor data collection and processing  
- Scheduled maintenance tasks
- Alert generation and notification

**Redis Integration:**
- Celery message broker and result backend
- Real-time data caching
- Session management for Socket.IO

### Database Schema Patterns

**Composition Pattern:**
- `TankMixes` contain multiple `MixComponents`
- Each `MixComponent` references a `Batch` with quantity tracking
- Dynamic composition calculation based on proportional weights

**Audit Trail Pattern:**
- All critical operations logged in `OperacjeLog`
- System changes tracked in `AuditTrail`
- Immutable history preservation for compliance

**Equipment State Management:**
- `Sprzet.active_mix_id` links current tank contents
- Temperature, pressure, level monitoring with history
- Valve state management for PathFinder integration

## Development Guidelines

### Working with Business Logic

**Batch Operations:**
- Always use `BatchManagementService` for transfers and mixing
- Validate equipment state before operations
- Handle balance corrections automatically with audit logging

**Process State Changes:**
- Use `WorkflowService` for state transitions
- Validate business rules (temperature, mix composition)
- Log all state changes with operator identification

**Equipment Operations:**
- Check PathFinder routes before transfers
- Validate valve states and resource availability
- Update equipment sensor data consistently

### Testing Patterns

**Service Layer Testing:**
- Mock database sessions for unit tests
- Test business rule validation thoroughly
- Verify audit trail creation in all operations

**Integration Testing:**
- Test complete process workflows end-to-end
- Validate PathFinder routing with real topology
- Test Socket.IO real-time updates

**Data Integrity:**
- Test composition calculations for accuracy
- Verify batch traceability through process chain
- Test balance correction mechanisms

### Configuration Management

**Environment-specific configs:**
- `Config` - Development configuration with debug enabled
- `ProdConfig` - Production with security headers and HTTPS
- `TestConfig` - Isolated test database and mock services

**Database Connection:**
- MySQL with connection pooling
- Alembic migrations for schema evolution
- Timezone-aware datetime handling (Warsaw/UTC)

### Performance Considerations

**Database Optimization:**
- Use `joinedload` for complex relationship queries
- Index frequently queried fields (equipment IDs, timestamps)
- Batch operations for bulk data processing

**Real-time Updates:**
- Efficient Socket.IO event filtering
- Redis pub/sub for cross-service communication
- Celery task optimization for sensor monitoring

### Security and Compliance

**Audit Requirements:**
- All production operations must be logged
- Operator identification required for critical actions
- Immutable audit trails for regulatory compliance

**Data Validation:**
- Temperature and pressure safety limits enforced
- Material compatibility checking before mixing
- Equipment state validation before operations

## Domain-Specific Rules

### Material Handling
- Raw materials arrive via Apollo melters or transport cisterns
- Each batch has immutable traceability (source, type, quantity)
- Mixing operations maintain proportional composition tracking
- Quality assessment determines process flow continuation

### Equipment Operations
- Reactors require 110°C minimum for bleaching earth addition
- Filters maintain cake status and contamination tracking
- Pipeline routing calculated dynamically based on valve states
- Temperature control with predictive heating models

### Process Validation
- Multi-stage filtration with circulation and transfer phases
- Quality sampling with operator assessment and automated routing
- Contamination prevention with equipment state validation
- Resource conflicts prevented (compressed air system exclusivity)

## Troubleshooting Common Issues

**PathFinder Route Failures:**
- Check valve states in database match physical plant
- Verify topology integrity in `Segmenty`/`PortySprzetu` tables
- Test with `pathfinder_tester.py` for debugging

**Temperature Control Issues:**
- Validate heating/cooling rate parameters in `Sprzet` table
- Check sensor service configuration and data updates
- Review heating history for model training data

**Batch Composition Errors:**
- Verify `MixComponents` quantities match expected totals
- Check for balance correction audit trails
- Validate batch transfer calculations in service methods

**Socket.IO Connection Problems:**
- Verify Redis connection for message persistence
- Check CORS configuration for frontend domains
- Monitor Celery worker status for real-time updates