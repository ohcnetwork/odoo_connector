from odoo.exceptions import AccessError, ValidationError
from odoo.http import request

from odoo import http

from ..authentication.authenticate_user import UserAuthentication
from ..resources.stock_monthly import MonthlyStockSync
from ..resources.stock_sync import StockSync


class CareStock(http.Controller):
    @http.route(
        "/api/stock/period", type="http", auth="public", methods=["POST"], csrf=False
    )
    def stock_period(self, **kwargs):
        try:
            env = UserAuthentication.get_authenticated_user(
                request.httprequest.headers.get("Authorization")
            )
            data = request.get_json_data()
            if not isinstance(data, dict):
                raise ValidationError("The stock request must be a JSON object.")
            actions = {
                "prepare": StockSync.prepare,
                "events": StockSync.events,
                "report": StockSync.report,
                "bill_sources": StockSync.bill_sources,
            }
            if data.get("mode") == "monthly":
                actions.update(
                    {
                        "prepare": MonthlyStockSync.prepare,
                        "events": MonthlyStockSync.events,
                        "close": MonthlyStockSync.close,
                        "snapshot": MonthlyStockSync.snapshot,
                        "status": MonthlyStockSync.status,
                        "publish": MonthlyStockSync.publish,
                        "current": MonthlyStockSync.current,
                    }
                )
            if data.get("action") not in actions:
                raise ValidationError("Unknown stock sync action.")
            with env.cr.savepoint():
                result = actions[data["action"]](env, data)
            return request.make_json_response({"success": True, **result})
        except AccessError as error:
            return request.make_json_response(
                {"success": False, "message": str(error)}, status=403
            )
        except (ValueError, KeyError, ValidationError) as error:
            return request.make_json_response(
                {"success": False, "message": str(error)}, status=400
            )
