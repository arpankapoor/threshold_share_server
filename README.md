## Problem Statement

Build an Android application for sharing images with a group of users. The
users should be able to upload images and specify the group of users with whom
the images are to be shared. Upon confirmation from the group, the image should
be encrypted and made available in their online repository and the key for
decryption should be shared among them. To decrypt a picture, a threshold
number of users should log in to the application within a time frame and input
their secret keys. The threshold number should be configured during image
upload by the owner of the image.

## Solution

The server is assumed to be a trusted third party.
The procedure is as follows:

1. New users register with `register_user`.
2. Send images to the server to be shared with a group of receivers.
   The server encrypts the image using AES with key _K_ and deletes the
   original This key _K_ is the split into as many subkeys as there are
   receivers (using [Shamir's Secret Sharing Scheme][ssss]).
3. Each receiver is sent their subkey and given an option to contribute the
   same for decryption of the shared image.
4. After the threshold number of subkeys are received, the original AES key
   _K_ can be restored and used to decrypt the image.
5. Finally the decrypted image is sent to all receivers.

## Software Used

- [Falcon Framework][falcon] - for the REST API.
- [peewee][peewee] - for Object Relational Mapping.
- [uwsgi][uwsgi] - Python WSGI server.
- [cryptography][crypto] - for AES encryption.
- [secretsharing][ss] - Shamir's secret sharing
  (Installed with `pip install git+git://github.com/EaterOA/secret-sharing.git`
  for Python3 compatibility)

## Server side API

### `get_user_list`

GET request.
*Output*: List of users in JSON

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

### `register_user`

POST request.
*Input*: Name and Mobile number.
*Output*: UserId, Name and MobileNumber

Example Input:

    {
      "mobilenumber": "+1234567890",
      "name": "abcd"
    }

Output:

    {
      "id": 123,
      "mobilenumber": "+1234567890",
      "name": "abcd"
    }

### `send_message`

*Input*: A POST request with JSON Object having following fields:

1. *receiver_ids*: List of User IDs of the receivers.
2. *sender_id*: User IDs of the sender.
3. *threshold_value*: The minimum number of subkeys required to decrypt the
   encrypted image.
4. *filename*: image filename.
5. *image*: base64 encoded image.

Example:

        {
            "receiver_ids": [2, 3, 4, 5, 6, 7, 8, 9, 10],
            "sender_id": 1,
            "threshold_value": 5,
            "filename": "bankkey.jpg",
            "image": "23y83y489yjkjfhhuhhfFDJKFKH"
        }

# Database Setup

1. Install MariaDB.

2. Run the following command.

        sudo mysql_install_db --user=mysql --basedir=/usr --datadir=/var/lib/mysql

3. Enable the MySQL service.

        sudo systemctl enable mysqld.service

4. Secure the installation.

        sudo mysql_secure_installation

5. Login as `root` and add a new database and user with the same name
   `threshold_share`.

        mysql -u root -p

        CREATE DATABASE threshold_share;
        CREATE USER 'threshold_share'@'localhost' IDENTIFIED BY '';
        GRANT ALL PRIVILEGES ON threshold_share.* TO 'threshold_share'@'localhost';
        FLUSH PRIVILEGES;
        quit;

6. Disable remote-access by uncommenting the following line from
   `/etc/mysql/my.cnf`:

        skip-networking

7. Find the unix socket location using the following.

        mysqladmin -u root -p variables | grep socket


[ssss]: http://doi.acm.org/10.1145/359168.359176
[falcon]: http://falconframework.org/
[peewee]: https://github.com/coleifer/peewee
[uwsgi]: https://uwsgi-docs.readthedocs.org/en/latest/
[crypto]: https://cryptography.io/en/latest/
[ss]: https://github.com/blockstack/secret-sharing
