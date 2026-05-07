import asyncpg

class SQLManager:
    def __init__(self):
        self.host = "sailing-postgres"
        self.port = 5432
        self.user = "sail"
        self.password = "sailpass"
        self.database = "sailing"

    async def create_connection(self):
        return await asyncpg.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database
        )

    async def fetch_data(self):
        connection = await self.create_connection()

        try:
            rows = await connection.fetch("SELECT * FROM polar_diagram_data;")

        finally:
            await connection.close()
        return rows

    async def add_data(self, tws, twa, boat_speed):
        connection = await self.create_connection()

        try:
            rows = await connection.execute(f"INSERT INTO polar_diagram_data (tws, twa, boat_speed)"
                                            f" VALUES ({tws}, {twa}, {boat_speed});")

        finally:
            await connection.close()
        return rows
