import models


class DbMiddleware:
    def process_request(self, req, resp):
        models.database.connect()
        tables = [models.User, models.Message, models.MessageToReceiver]
        models.database.create_tables(tables, safe=True)

    def process_response(self, req, resp, resource):
        if not models.database.is_closed():
            models.database.close()
