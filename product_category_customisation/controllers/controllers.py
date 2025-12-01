# -*- coding: utf-8 -*-
# from odoo import http


# class EvolvHelpdesk(http.Controller):
#     @http.route('/evolv_helpdesk/evolv_helpdesk', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/evolv_helpdesk/evolv_helpdesk/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('evolv_helpdesk.listing', {
#             'root': '/evolv_helpdesk/evolv_helpdesk',
#             'objects': http.request.env['evolv_helpdesk.evolv_helpdesk'].search([]),
#         })

#     @http.route('/evolv_helpdesk/evolv_helpdesk/objects/<model("evolv_helpdesk.evolv_helpdesk"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('evolv_helpdesk.object', {
#             'object': obj
#         })

