# SensorPlaces

A repository for managing and tracking IoT sensor locations and their associated metadata.

## Description

SensorPlaces provides tools and infrastructure for organizing, managing, and visualizing IoT sensor deployments across different locations.

## Getting Started

### Running with Docker

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/sensorplaces.git
   cd sensorplaces
   ```

2. Run the setup script to create the environment file:
   ```
   ./setup-local-env.sh
   ```

3. Build and start the containers:
   ```
   docker-compose up -d
   ```

4. Access the application at http://localhost:8000

### Development Mode

For development with hot-reloading:

```
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

## Features

- Tracking of sensor locations and metadata
- Integration with InfluxDB for sensor data storage
- User authentication and authorization
- Map-based visualization of sensor deployments

## License

This project is part of the SheerIoT organization. 