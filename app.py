import falcon
import middleware as mw
import resources

api = application = falcon.API(middleware=[
    mw.DbMiddleware()
])

users = resources.UsersResource()
user_reg = resources.UserRegisterationResource()
send_msg = resources.SendMessageResource()
get_msgs = resources.GetMessagesResource()
send_key = resources.SendKeyResource()

api.add_route("/get_user_list", users)
api.add_route("/register_user", user_reg)
api.add_route("/send_message", send_msg)
api.add_route("/get_messages", get_msgs)
api.add_route("/send_key", send_key)
