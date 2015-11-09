import falcon
import middleware as mw
import resources

api = application = falcon.API(middleware=[
    mw.DbMiddleware()
])

users = resources.UsersResource()
user_reg = resources.UserRegisterationResource()
send_msg = resources.SendMessageResource()

api.add_route("/get_user_list", users)
api.add_route("/reg_user", user_reg)
api.add_route("/send_msg", send_msg)
