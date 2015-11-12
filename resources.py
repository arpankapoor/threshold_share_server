import base64
import datetime
import enc
import falcon
import json
import os
import models as md
import playhouse.shortcuts as ps

IMAGES_DIRECTORY = "./images/"
THRESHOLD_MINUTES = 10


class UsersResource:
    """
    Return list of all registered users in JSON.

    Example:

        [
            {
                "id": 1,
                "name": "abcd"
            },
            {
                "id": 2,
                "name": "dcba"
            }
        ]
    """

    def on_get(self, req, resp):
        users = md.User.select()
        users_dict = [ps.model_to_dict(user) for user in users]
        resp.body = json.dumps(users_dict)


class UserRegisterationResource:
    """
    Register a new user.
    Input JSON:

        {
            "name": "ABCD"
        }

    Output JSON:

        {
            "id": 1,
            "name": "ABCD",
        }

    If any error occurs, set id = -1
    """

    def on_post(self, req, resp):
        try:
            user_dict = json.loads(req.stream.read().decode())
        except ValueError:
            user = md.User(id=-1)
            resp.body = json.dumps(ps.model_to_dict(user))
        else:
            # Don't recreate if already existing...
            user = md.User.create(name=user_dict.get("name", ""))

            resp.body = json.dumps(ps.model_to_dict(user))


class SendMessageResource:
    """
    Send an image to a group of users.

    Input: A POST request with JSON Object having following fields:
        1. receiver_ids: List of User IDs of the receivers.
        2. sender_id: User IDs of the sender.
        3. threshold_value: The minimum number of subkeys required to
            decrypt the encrypted image.
        4. filename: image filename.
        5. image: base64 encoded image.

    Example:

        {
            "receiver_ids": [2, 3, 4, 5, 6, 7, 8, 9, 10],
            "sender_id": 1,
            "threshold_value": 5,
            "filename": "bankkey.jpg",
            "image": "23y83y489yjkjfhhuhhfFDJKFKH"
        }
    """

    def decode_metadata(self, jsonStr):
        """
        Return a 4 tuple:
            receivers -> list of User md with ids from "receiver_ids"
            sender -> sending User
            thresholdValue -> int
            filename -> string
            image -> bytes
        """

        # TODO: Error checks!!
        metadata = json.loads(jsonStr)

        sender = md.User.get(md.User.id == metadata.get("sender_id", -1))

        # We assume that all the receivers exist...
        receivers = [md.User.get(md.User.id == rcvr_id)
                     for rcvr_id in metadata.get("receiver_ids", [])]

        # The sender is an implicit receiver
        receivers.append(sender)

        thresh_number = min(len(receivers),
                            metadata.get("threshold_value", 100))

        filename = metadata.get("filename", "NO_NAME.jpg")

        image = metadata.get("image")
        image = base64.b64decode(image)

        return (receivers, sender, thresh_number, filename, image)

    def save_image(self, img_data, filename):

        os.makedirs(IMAGES_DIRECTORY, exist_ok=True)

        path = os.path.join(IMAGES_DIRECTORY + filename)
        with open(path, "wb") as f:
            f.write(img_data)

    def on_post(self, req, resp):
        json_str = req.stream.read().decode()

        # Decode metadata
        rcvrs, sndr, thrsh_no, filename, img = self.decode_metadata(json_str)

        # Encrypt the image and split the key using Shamir's secret sharing.
        # The image can be decrypted with the threshold number of subkeys.
        keys, encrypted_img = enc.encrypt_and_split(img, thrsh_no, len(rcvrs))

        # DB blob
        msg = md.Message.create(sender=sndr, threshold_number=thrsh_no,
                                filename=filename)

        self.save_image(encrypted_img, str(msg.id))

        # Create a MessageToReceiver object for each of the receivers
        for key, receiver in zip(keys, rcvrs):
            md.MessageToReceiver.create(message=msg, receiver=receiver,
                                        subkey=key)


class GetMessagesResource:
    """
    Get all the pending messages corresponding to a user.
    Input: A POST request with the userId in JSON.
    {
        "id": 12
    }
    Output: List of pending messages.
    The *type* field indicates what data is inside the *data* field

    [
        {
            "message_id": 3,
            "sender_id": 2,
            "type": "image",
            "filename": "xyz.jpg",
            "data": "base64imagedata"
        },
        {
            "message_id": 5,
            "sender_id": 1,
            "type": "key",
            "filename": "xyz.jpg",
            "data": "subkey"
        },
    ]
    """

    def create_resp_msg(self, msg_id, sndr_id, data_type, filename, data):
        """Return a dictionary with the response fields set accordingly."""

        return {
                    "message_id": msg_id,
                    "sender_id": sndr_id,
                    "data_type": data_type,
                    "filename": filename,
                    "data": data
               }

    def get_img(self, msg_id):
        """
        Return the image corresponding to a
        message as a base64 encoded string.
        """
        path = os.path.join(IMAGES_DIRECTORY + str(msg_id))
        data = None

        with open(path, "rb") as f:
            data = f.read()

        data = base64.b64encode(data)
        return data.decode()

    def on_post(self, req, resp):
        json_dict = json.loads(req.stream.read().decode())
        user_id = json_dict.get("id", 0)

        user = md.User.get(md.User.id == user_id)

        query = (md.MessageToReceiver
                 .select(md.MessageToReceiver, md.Message)
                 .join(md.Message)
                 .where(md.MessageToReceiver.receiver == user))

        resp_msgs = []
        for msg_to_rcvr in query:
            msg = msg_to_rcvr.message
            if not msg.is_encrypted:
                # Send message
                resp_msgs.append(self.create_resp_msg(
                    msg.id, msg.sender_id, "image",
                    msg.filename, self.get_img(msg.id)))

                # Delete the MessageToReceiver entry
                msg_to_rcvr.delete_instance()

            elif msg_to_rcvr.status == md.KeyStatus.not_sent:
                # Send key
                resp_msgs.append(self.create_resp_msg(
                    msg.id, msg.sender_id, "key",
                    msg.filename, msg_to_rcvr.subkey))

                # Change status to key_sent
                msg_to_rcvr.subkey = ""
                msg_to_rcvr.status = md.KeyStatus.sent
                msg_to_rcvr.save()

        # Send a 204 No Content status if there are no messages
        if len(resp_msgs) == 0:
            resp.status = falcon.HTTP_204
        else:
            resp.body = json.dumps(resp_msgs)


class SendKeyResource:
    """
    Receives a key from user

    Input: A POST request with JSON Object having following fields:
    1. sender_id: User ID of the sender
    2. message_id: Message ID of the image
    3. key: key of user

    Example:

    {
        "sender_id": 1,
        "message_id": 1,
        "key": "1-nlkdnfgklndslkgnlkdnlfglkdnflk"
    }
    """

    def decode_metadata(self, jsonStr):
        """
        Return a 3 tuple:
            sender_id -> sending User
            message_id -> Message Id
            key -> string
        """
        metadata = json.loads(jsonStr)

        sender = md.User.get(md.User.id == metadata.get("sender_id", -1))
        message = md.Message.get(md.Message.id == metadata.get("message_id", -1))
        key = metadata.get("key","")
        return (sender, message, key)

    def get_subkeys(self, message):
        MTR = md.MessageToReceiver
        threshold_mtr = MTR.select().where(MTR.message == message.id, MTR.status == md.KeyStatus.recvd)

        subkeys = []
        for mtr in threshold_mtr:
            subkeys.append(mtr.subkey)

        return subkeys

    def get_img(self, msg_id):
        path = os.path.join(IMAGES_DIRECTORY + str(msg_id))
        data = None

        with open(path, "rb") as f:
            data = f.read()

        return data

    def save_image(self, img_data, filename):

        os.makedirs(IMAGES_DIRECTORY, exist_ok=True)

        path = os.path.join(IMAGES_DIRECTORY + filename)
        with open(path, "wb") as f:
            f.write(img_data)

    def decrypt_image(self,subkeys,msg_id):

        data = self.get_img(msg_id)
        decrypted_data = enc.combine_and_decrypt(data, subkeys)

        self.save_image(decrypted_data,str(msg_id))


    def on_post(self, req, resp):
        json_str = req.stream.read().decode()

        sender, message, key = self.decode_metadata(json_str)
        MTR = md.MessageToReceiver
        msgtorecv = MTR.get(MTR.receiver == sender.id, MTR.message == message.id)

        # Checking status is sent or not
        if msgtorecv.status == md.KeyStatus.sent:
            msgtorecv.status = md.KeyStatus.recvd
            msgtorecv.subkey = key
            msgtorecv.save()

            if message.number_of_subkeys == 0:
                message.valid_till = datetime.datetime.now() + datetime.timedelta(minutes = THRESHOLD_MINUTES)
            elif message.number_of_subkeys == message.threshold_number-1:
                message.is_encrypted = False

                subkeys = self.get_subkeys(message)

                self.decrypt_image(subkeys,message.id)

            message.number_of_subkeys = message.number_of_subkeys + 1
            message.save()
