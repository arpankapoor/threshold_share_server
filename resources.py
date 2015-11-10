import cgi
import datetime
import enc
import imghdr
import json
import models as md
import playhouse.shortcuts as ps


class UsersResource:
    """
    Return list of all registered users in JSON.

    Example:

        [
            {
                "id": 1,
                "mobilenumber": "+1234567890",
                "name": "abcd"
            },
            {
                "id": 2,
                "mobilenumber": "+9876543210",
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
            "mobilenumber": "+1234567890"
        }

    Output JSON:

        {
            "id": 1,
            "name": "ABCD",
            "mobilenumber": "+1234567890"
        }

    If any error occurs, set id = -1
    """

    def on_post(self, req, resp):
        # TODO: check if mobilenumber == "" and do appropriate stuff
        try:
            user_dict = json.loads(req.stream.read().decode())
        except ValueError:
            user = md.User(id=-1)
            resp.body = json.dumps(ps.model_to_dict(user))
        else:
            # Don't recreate if already existing...
            user, created = md.User.get_or_create(
                    mobilenumber=user_dict.get("mobilenumber", ""),
                    defaults={"name": user_dict.get("name", "")})

            # Update the name
            if not created:
                user.name = user_dict.get("name", user.name)
                user.save()

            resp.body = json.dumps(ps.model_to_dict(user))


class SendMessageResource:
    """
    Send an image to a group of users.

    Input: A POST request with Content-Type multipart/form-data.
    The form has 2 key value pairs:

    1. Metadata with the following fields in JSON:
        1. receiver_ids: List of User IDs of the receivers.
        2. sender_id: User IDs of the sender.
        3. thresh_number: The minimum number of subkeys required to
           decrypt the encrypted image.
        4. thresh_time: The time frame within which the threshold number of
           subkeys should be available.
    2. The image file.

    Example:

        metadata={
                    "receiver_ids": [2, 3, 4, 5, 6, 7, 8, 9, 10],
                    "sender_id": 1,
                    "thresh_number": 5,
                    "thresh_time": 3600
                 }
        image=file
    """

    def decode_metadata(self, metadata_json):
        """
        Return a 4 tuple:
            receivers -> list of User md with ids from "receiver_ids"
            sender -> sending User
            thresh_number -> int
            valid_till -> datetime object = thresh_time + current_time
        """

        # TODO: Error checks!!
        metadata = json.loads(metadata_json)

        sender = md.User.get(md.User.id == metadata.get("sender_id", -1))

        # We assume that all the receivers exist...
        receivers = [md.User.get(md.User.id == rcvr_id)
                     for rcvr_id in metadata.get("receiver_ids", [])]

        # The sender is an implicit receiver
        receivers.append(sender)

        # Default: 1 day
        thresh_time = metadata.get("thresh_hours", 86400)
        valid_till = (datetime.datetime.now() +
                      datetime.timedelta(hours=thresh_time))

        thresh_number = min(len(receivers),
                            metadata.get("thresh_number", 100))

        return (receivers, sender, thresh_number, valid_till)

    def on_post(self, req, resp):
        if "multipart/form-data" not in req.content_type:
            return

        try:
            form = cgi.FieldStorage(fp=req.stream, environ=req.env)
        except:
            return

        metadata_json = form.getfirst("metadata")
        img_data = form.getfirst("image")

        img_type = imghdr.what("", h=img_data)

        # Decode metadata
        rcvrs, sndr, thrsh_no, valid_till = self.decode_metadata(metadata_json)

        # Encrypt the image and split the key using Shamir's secret sharing.
        # The image can be decrypted with the threshold number of subkeys.
        keys, encrypted_img = enc.encrypt_and_split(img_data, thrsh_no,
                                                    len(rcvrs))

        # DB blob
        img = md.Image.create(img_data=encrypted_img, img_type=img_type,
                              is_encrypted=True)

        msg = md.Message.create(sender=sndr, threshold_number=thrsh_no,
                                image=img, valid_till=valid_till)

        # Create a MessageToReceiver object for each of the receivers
        for key, receiver in zip(keys, rcvrs):
            md.MessageToReceiver.create(message=msg, receiver=receiver,
                                        subkey=key)
