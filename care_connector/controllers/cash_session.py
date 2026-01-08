import json
from odoo import http
from odoo.http import request
from ..authentication.authenticate_user import UserAuthentication
from ..pydantic_models.cash_session import (
    OpenSessionRequest,
    CloseSessionRequest,
    SessionListRequest,
    CreateTransferRequest,
    AcceptTransferRequest,
    RejectTransferRequest,
    CancelTransferRequest,
    TransferListRequest,
    PendingTransfersRequest,
)
from ..resources.cash_session import CashSessionUtility


class CashSessionController(http.Controller):
    """API endpoints for cash session management."""

    # === SESSION ENDPOINTS ===

    @http.route('/api/care/cash/session', type='http', auth='public', methods=['POST'], csrf=False)
    def open_session(self, **kwargs):
        """Open a new cash session."""
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = OpenSessionRequest(**data)

            result = CashSessionUtility.open_session(user_env, request_data)

            return request.make_json_response({
                "success": True,
                "message": "Session opened successfully",
                "session": result
            }, status=200)

        except ValueError as e:
            return request.make_json_response({
                "success": False,
                "error_type": "ValueError",
                "message": str(e)
            }, status=400)

        except Exception as err:
            return request.make_json_response({
                "success": False,
                "error_type": "ServerError",
                "message": f"Unexpected error: {str(err)}"
            }, status=500)

    @http.route('/api/care/cash/session/close', type='http', auth='public', methods=['PUT', 'POST'], csrf=False)
    def close_session(self, **kwargs):
        """Close an existing cash session."""
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = CloseSessionRequest(**data)

            result = CashSessionUtility.close_session(user_env, request_data)

            return request.make_json_response({
                "success": True,
                "message": "Session closed successfully",
                "session": result
            }, status=200)

        except ValueError as e:
            return request.make_json_response({
                "success": False,
                "error_type": "ValueError",
                "message": str(e)
            }, status=400)

        except Exception as err:
            return request.make_json_response({
                "success": False,
                "error_type": "ServerError",
                "message": f"Unexpected error: {str(err)}"
            }, status=500)

    @http.route('/api/care/cash/session/current', type='http', auth='public', methods=['POST'], csrf=False)
    def get_current_session(self, **kwargs):
        """Get the current open session for a user at a counter."""
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)

            data = json.loads(request.httprequest.data) if request.httprequest.data else {}
            external_user_id = data.get('external_user_id')
            counter_x_care_id = data.get('counter_x_care_id')

            if not external_user_id or not counter_x_care_id:
                return request.make_json_response({
                    "success": False,
                    "error_type": "ValueError",
                    "message": "external_user_id and counter_x_care_id are required"
                }, status=400)

            result = CashSessionUtility.get_current_session(
                user_env, external_user_id, counter_x_care_id
            )

            if result is None:
                return request.make_json_response({
                    "success": True,
                    "message": "No open session found",
                    "session": None
                }, status=200)

            return request.make_json_response({
                "success": True,
                "session": result
            }, status=200)

        except ValueError as e:
            return request.make_json_response({
                "success": False,
                "error_type": "ValueError",
                "message": str(e)
            }, status=400)

        except Exception as err:
            return request.make_json_response({
                "success": False,
                "error_type": "ServerError",
                "message": f"Unexpected error: {str(err)}"
            }, status=500)

    @http.route('/api/care/cash/session/list', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def list_sessions(self, **kwargs):
        """List sessions with optional filters."""
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)

            # Support both GET params and POST body
            if request.httprequest.method == 'POST':
                data = json.loads(request.httprequest.data) if request.httprequest.data else {}
            else:
                data = {
                    'external_user_id': kwargs.get('external_user_id'),
                    'counter_x_care_id': kwargs.get('counter_x_care_id'),
                    'status': kwargs.get('status'),
                    'limit': int(kwargs.get('limit', 50)),
                    'offset': int(kwargs.get('offset', 0)),
                }

            request_data = SessionListRequest(**data)
            result = CashSessionUtility.list_sessions(user_env, request_data)

            return request.make_json_response({
                "success": True,
                "sessions": result,
                "count": len(result)
            }, status=200)

        except ValueError as e:
            return request.make_json_response({
                "success": False,
                "error_type": "ValueError",
                "message": str(e)
            }, status=400)

        except Exception as err:
            return request.make_json_response({
                "success": False,
                "error_type": "ServerError",
                "message": f"Unexpected error: {str(err)}"
            }, status=500)

    # === TRANSFER ENDPOINTS ===

    @http.route('/api/care/cash/transfer', type='http', auth='public', methods=['POST'], csrf=False)
    def create_transfer(self, **kwargs):
        """Create a new cash transfer."""
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = CreateTransferRequest(**data)

            result = CashSessionUtility.create_transfer(user_env, request_data)

            return request.make_json_response({
                "success": True,
                "message": "Transfer created successfully",
                "transfer": result
            }, status=200)

        except ValueError as e:
            return request.make_json_response({
                "success": False,
                "error_type": "ValueError",
                "message": str(e)
            }, status=400)

        except Exception as err:
            return request.make_json_response({
                "success": False,
                "error_type": "ServerError",
                "message": f"Unexpected error: {str(err)}"
            }, status=500)

    @http.route('/api/care/cash/transfer/<int:transfer_id>/accept', type='http', auth='public', methods=['PUT', 'POST'], csrf=False)
    def accept_transfer(self, transfer_id, **kwargs):
        """Accept a pending transfer."""
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = AcceptTransferRequest(**data)

            result = CashSessionUtility.accept_transfer(user_env, transfer_id, request_data)

            return request.make_json_response({
                "success": True,
                "message": "Transfer accepted successfully",
                "transfer": result
            }, status=200)

        except ValueError as e:
            return request.make_json_response({
                "success": False,
                "error_type": "ValueError",
                "message": str(e)
            }, status=400)

        except Exception as err:
            return request.make_json_response({
                "success": False,
                "error_type": "ServerError",
                "message": f"Unexpected error: {str(err)}"
            }, status=500)

    @http.route('/api/care/cash/transfer/<int:transfer_id>/reject', type='http', auth='public', methods=['PUT', 'POST'], csrf=False)
    def reject_transfer(self, transfer_id, **kwargs):
        """Reject a pending transfer."""
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = RejectTransferRequest(**data)

            result = CashSessionUtility.reject_transfer(user_env, transfer_id, request_data)

            return request.make_json_response({
                "success": True,
                "message": "Transfer rejected successfully",
                "transfer": result
            }, status=200)

        except ValueError as e:
            return request.make_json_response({
                "success": False,
                "error_type": "ValueError",
                "message": str(e)
            }, status=400)

        except Exception as err:
            return request.make_json_response({
                "success": False,
                "error_type": "ServerError",
                "message": f"Unexpected error: {str(err)}"
            }, status=500)

    @http.route('/api/care/cash/transfer/<int:transfer_id>/cancel', type='http', auth='public', methods=['PUT', 'POST'], csrf=False)
    def cancel_transfer(self, transfer_id, **kwargs):
        """Cancel a pending transfer (by the sender)."""
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)
            data = json.loads(request.httprequest.data)
            request_data = CancelTransferRequest(**data)

            result = CashSessionUtility.cancel_transfer(user_env, transfer_id, request_data)

            return request.make_json_response({
                "success": True,
                "message": "Transfer cancelled successfully",
                "transfer": result
            }, status=200)

        except ValueError as e:
            return request.make_json_response({
                "success": False,
                "error_type": "ValueError",
                "message": str(e)
            }, status=400)

        except Exception as err:
            return request.make_json_response({
                "success": False,
                "error_type": "ServerError",
                "message": f"Unexpected error: {str(err)}"
            }, status=500)

    @http.route('/api/care/cash/transfer/list', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def list_transfers(self, **kwargs):
        """List transfers with optional filters."""
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)

            # Support both GET params and POST body
            if request.httprequest.method == 'POST':
                data = json.loads(request.httprequest.data) if request.httprequest.data else {}
            else:
                data = {
                    'from_session_id': int(kwargs['from_session_id']) if kwargs.get('from_session_id') else None,
                    'to_session_id': int(kwargs['to_session_id']) if kwargs.get('to_session_id') else None,
                    'status': kwargs.get('status'),
                    'limit': int(kwargs.get('limit', 50)),
                    'offset': int(kwargs.get('offset', 0)),
                }

            request_data = TransferListRequest(**data)
            result = CashSessionUtility.list_transfers(user_env, request_data)

            return request.make_json_response({
                "success": True,
                "transfers": result,
                "count": len(result)
            }, status=200)

        except ValueError as e:
            return request.make_json_response({
                "success": False,
                "error_type": "ValueError",
                "message": str(e)
            }, status=400)

        except Exception as err:
            return request.make_json_response({
                "success": False,
                "error_type": "ServerError",
                "message": f"Unexpected error: {str(err)}"
            }, status=500)

    @http.route('/api/care/cash/transfer/pending', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def get_pending_transfers(self, **kwargs):
        """Get pending transfers for a session (incoming)."""
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)

            # Support both GET params and POST body
            if request.httprequest.method == 'POST':
                data = json.loads(request.httprequest.data) if request.httprequest.data else {}
            else:
                data = {
                    'external_user_id': kwargs.get('external_user_id'),
                    'counter_x_care_id': kwargs.get('counter_x_care_id'),
                }

            request_data = PendingTransfersRequest(**data)
            result = CashSessionUtility.get_pending_transfers(user_env, request_data)

            return request.make_json_response({
                "success": True,
                "transfers": result,
                "count": len(result)
            }, status=200)

        except ValueError as e:
            return request.make_json_response({
                "success": False,
                "error_type": "ValueError",
                "message": str(e)
            }, status=400)

        except Exception as err:
            return request.make_json_response({
                "success": False,
                "error_type": "ServerError",
                "message": f"Unexpected error: {str(err)}"
            }, status=500)

    # === COUNTER ENDPOINTS ===

    @http.route('/api/care/cash/counters', type='http', auth='public', methods=['GET'], csrf=False)
    def list_counters(self, **kwargs):
        """List all available counters."""
        try:
            auth_header = request.httprequest.headers.get("Authorization")
            user_env = UserAuthentication.get_authenticated_user(auth_header)

            result = CashSessionUtility.list_counters(user_env)

            return request.make_json_response({
                "success": True,
                "counters": result,
                "count": len(result)
            }, status=200)

        except ValueError as e:
            return request.make_json_response({
                "success": False,
                "error_type": "ValueError",
                "message": str(e)
            }, status=400)

        except Exception as err:
            return request.make_json_response({
                "success": False,
                "error_type": "ServerError",
                "message": f"Unexpected error: {str(err)}"
            }, status=500)
