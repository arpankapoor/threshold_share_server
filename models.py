from enum import IntEnum
import peewee as pw

dbname = "threshold_share"
dbuser = dbname
database = pw.MySQLDatabase(dbname, user=dbuser,
                            unix_socket="/run/mysqld/mysqld.sock")


class KeyStatus(IntEnum):
    not_sent, sent, recvd = range(3)


class KeyStatusField(pw.IntegerField):
    def db_value(self, value):
        return int(value)

    def python_value(self, value):
        for status in KeyStatus:
            if value == status:
                return status


class BaseModel(pw.Model):
    class Meta:
        database = database


class User(BaseModel):
    name = pw.CharField(max_length=100)
    mobilenumber = pw.CharField(max_length=30, unique=True)


class Image(BaseModel):
    img_data = pw.BlobField()
    img_type = pw.CharField(max_length=10)
    is_encrypted = pw.BooleanField(default=False)


class Message(BaseModel):
    sender = pw.ForeignKeyField(User)
    image = pw.ForeignKeyField(Image)
    threshold_number = pw.IntegerField()
    valid_till = pw.DateTimeField()


class MessageToReceiver(BaseModel):
    message = pw.ForeignKeyField(Message)
    receiver = pw.ForeignKeyField(User)
    subkey = pw.CharField()
    status = KeyStatusField(default=KeyStatus.not_sent)

    class Meta:
        primary_key = pw.CompositeKey("message", "receiver")
