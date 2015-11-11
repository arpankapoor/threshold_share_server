import base64
import enc
import json
import os
import models as md
import playhouse.shortcuts as ps


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
        images_directory = "./images/"

        os.makedirs(images_directory, exist_ok=True)

        path = os.path.join(images_directory + filename)
        f = open(path, "wb")
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
