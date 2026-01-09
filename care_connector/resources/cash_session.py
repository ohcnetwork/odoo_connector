from odoo import fields


class CashSessionUtility:
    """Business logic for cash session and transfer operations."""

    @classmethod
    def open_session(cls, user_env, request_data):
        """Open a new cash session."""
        try:
            cash_session_model = user_env['cash.session']
            bill_counter_model = user_env['bill.counter']

            # Find the counter
            counter = bill_counter_model.search([
                ('x_care_id', '=', request_data.counter_x_care_id)
            ], limit=1)

            if not counter:
                raise ValueError(f"Counter not found: {request_data.counter_x_care_id}")

            # Check for existing open session
            existing = cash_session_model.search([
                ('external_user_id', '=', request_data.external_user_id),
                ('counter_id', '=', counter.id),
                ('status', '=', 'open')
            ], limit=1)

            if existing:
                raise ValueError(
                    f"User {request_data.external_user_id} already has an open session "
                    f"at counter {request_data.counter_x_care_id}"
                )

            # Create session
            session = cash_session_model.create({
                'external_user_id': request_data.external_user_id,
                'external_user_name': request_data.external_user_name,
                'counter_id': counter.id,
                'opening_balance': request_data.opening_balance,
                'status': 'open',
            })

            return cls._session_to_dict(session)

        except Exception as e:
            raise ValueError(str(e))

    @classmethod
    def close_session(cls, user_env, request_data):
        """Close an existing cash session."""
        try:
            cash_session_model = user_env['cash.session']
            bill_counter_model = user_env['bill.counter']

            # Find the counter
            counter = bill_counter_model.search([
                ('x_care_id', '=', request_data.counter_x_care_id)
            ], limit=1)

            if not counter:
                raise ValueError(f"Counter not found: {request_data.counter_x_care_id}")

            # Find open session
            session = cash_session_model.search([
                ('external_user_id', '=', request_data.external_user_id),
                ('counter_id', '=', counter.id),
                ('status', '=', 'open')
            ], limit=1)

            if not session:
                raise ValueError(
                    f"No open session found for user {request_data.external_user_id} "
                    f"at counter {request_data.counter_x_care_id}"
                )

            # Close the session
            session.action_close(
                closed_by_ext_id=request_data.closed_by_ext_id,
                closed_by_name=request_data.closed_by_name
            )

            return cls._session_to_dict(session)

        except Exception as e:
            raise ValueError(str(e))

    @classmethod
    def get_current_session(cls, user_env, external_user_id, counter_x_care_id):
        """Get the current open session for a user at a counter."""
        try:
            cash_session_model = user_env['cash.session']
            bill_counter_model = user_env['bill.counter']

            # Find the counter
            counter = bill_counter_model.search([
                ('x_care_id', '=', counter_x_care_id)
            ], limit=1)

            if not counter:
                return None

            # Find open session
            session = cash_session_model.search([
                ('external_user_id', '=', external_user_id),
                ('counter_id', '=', counter.id),
                ('status', '=', 'open')
            ], limit=1)

            if not session:
                return None

            return cls._session_to_dict(session)

        except Exception as e:
            raise ValueError(str(e))

    @classmethod
    def list_sessions(cls, user_env, request_data):
        """List sessions with optional filters."""
        try:
            cash_session_model = user_env['cash.session']
            bill_counter_model = user_env['bill.counter']

            domain = []

            if request_data.external_user_id:
                domain.append(('external_user_id', '=', request_data.external_user_id))

            if request_data.counter_x_care_id:
                counter = bill_counter_model.search([
                    ('x_care_id', '=', request_data.counter_x_care_id)
                ], limit=1)
                if counter:
                    domain.append(('counter_id', '=', counter.id))

            if request_data.status:
                domain.append(('status', '=', request_data.status))

            sessions = cash_session_model.search(
                domain,
                limit=request_data.limit,
                offset=request_data.offset,
                order='opened_at desc'
            )

            return [cls._session_to_dict(s) for s in sessions]

        except Exception as e:
            raise ValueError(str(e))

    @classmethod
    def create_transfer(cls, user_env, request_data):
        """Create a new cash transfer."""
        try:
            cash_session_model = user_env['cash.session']
            cash_transfer_model = user_env['cash.transfer']
            bill_counter_model = user_env['bill.counter']

            # Find from session
            from_counter = bill_counter_model.search([
                ('x_care_id', '=', request_data.from_counter_x_care_id)
            ], limit=1)
            if not from_counter:
                raise ValueError(f"From counter not found: {request_data.from_counter_x_care_id}")

            from_session = cash_session_model.search([
                ('external_user_id', '=', request_data.from_user_id),
                ('counter_id', '=', from_counter.id),
                ('status', '=', 'open')
            ], limit=1)
            if not from_session:
                raise ValueError(
                    f"No open session for user {request_data.from_user_id} "
                    f"at counter {request_data.from_counter_x_care_id}"
                )

            # Find to session by ID
            to_session = cash_session_model.browse(request_data.to_session_id)
            if not to_session.exists():
                raise ValueError(f"Target session not found: {request_data.to_session_id}")
            if to_session.status != 'open':
                raise ValueError(
                    f"Target session {request_data.to_session_id} is not open "
                    f"(status: {to_session.status})"
                )

            # Create transfer
            transfer = cash_transfer_model.create({
                'from_session_id': from_session.id,
                'to_session_id': to_session.id,
                'amount': request_data.amount,
                'denominations': request_data.denominations,
                'created_by_ext_id': request_data.created_by_ext_id,
                'created_by_name': request_data.created_by_name,
            })

            return cls._transfer_to_dict(transfer)

        except Exception as e:
            raise ValueError(str(e))

    @classmethod
    def accept_transfer(cls, user_env, transfer_id, request_data):
        """Accept a pending transfer."""
        try:
            cash_transfer_model = user_env['cash.transfer']

            transfer = cash_transfer_model.browse(transfer_id)
            if not transfer.exists():
                raise ValueError(f"Transfer not found: {transfer_id}")

            # Validate session_id matches the transfer's destination session
            if transfer.to_session_id.id != request_data.session_id:
                raise ValueError(
                    f"Session ID mismatch. Only the destination session can accept this transfer."
                )

            transfer.action_accept(
                resolved_by_ext_id=request_data.resolved_by_ext_id,
                resolved_by_name=request_data.resolved_by_name
            )

            return cls._transfer_to_dict(transfer)

        except Exception as e:
            raise ValueError(str(e))

    @classmethod
    def reject_transfer(cls, user_env, transfer_id, request_data):
        """Reject a pending transfer."""
        try:
            cash_transfer_model = user_env['cash.transfer']

            transfer = cash_transfer_model.browse(transfer_id)
            if not transfer.exists():
                raise ValueError(f"Transfer not found: {transfer_id}")

            # Validate session_id matches the transfer's destination session
            if transfer.to_session_id.id != request_data.session_id:
                raise ValueError(
                    f"Session ID mismatch. Only the destination session can reject this transfer."
                )

            transfer.action_reject(
                resolved_by_ext_id=request_data.resolved_by_ext_id,
                resolved_by_name=request_data.resolved_by_name,
                reason=request_data.reason
            )

            return cls._transfer_to_dict(transfer)

        except Exception as e:
            raise ValueError(str(e))

    @classmethod
    def cancel_transfer(cls, user_env, transfer_id, request_data):
        """Cancel a pending transfer (by the sender)."""
        try:
            cash_transfer_model = user_env['cash.transfer']

            transfer = cash_transfer_model.browse(transfer_id)
            if not transfer.exists():
                raise ValueError(f"Transfer not found: {transfer_id}")

            transfer.action_cancel(
                cancelled_by_ext_id=request_data.cancelled_by_ext_id,
                cancelled_by_name=request_data.cancelled_by_name,
                reason=request_data.reason
            )

            return cls._transfer_to_dict(transfer)

        except Exception as e:
            raise ValueError(str(e))

    @classmethod
    def list_transfers(cls, user_env, request_data):
        """List transfers with optional filters."""
        try:
            cash_transfer_model = user_env['cash.transfer']

            domain = []

            if request_data.from_session_id:
                domain.append(('from_session_id', '=', request_data.from_session_id))

            if request_data.to_session_id:
                domain.append(('to_session_id', '=', request_data.to_session_id))

            if request_data.status:
                domain.append(('status', '=', request_data.status))

            transfers = cash_transfer_model.search(
                domain,
                limit=request_data.limit,
                offset=request_data.offset,
                order='created_at desc'
            )

            return [cls._transfer_to_dict(t) for t in transfers]

        except Exception as e:
            raise ValueError(str(e))

    @classmethod
    def get_pending_transfers(cls, user_env, request_data):
        """Get pending transfers for a session (incoming)."""
        try:
            cash_session_model = user_env['cash.session']
            cash_transfer_model = user_env['cash.transfer']
            bill_counter_model = user_env['bill.counter']

            # Find counter and session
            counter = bill_counter_model.search([
                ('x_care_id', '=', request_data.counter_x_care_id)
            ], limit=1)
            if not counter:
                return []

            session = cash_session_model.search([
                ('external_user_id', '=', request_data.external_user_id),
                ('counter_id', '=', counter.id),
                ('status', '=', 'open')
            ], limit=1)
            if not session:
                return []

            # Get pending incoming transfers
            transfers = cash_transfer_model.search([
                ('to_session_id', '=', session.id),
                ('status', '=', 'pending')
            ], order='created_at desc')

            return [cls._transfer_to_dict(t) for t in transfers]

        except Exception as e:
            raise ValueError(str(e))

    @classmethod
    def list_counters(cls, user_env):
        """List all available counters with their session status."""
        try:
            bill_counter_model = user_env['bill.counter']
            cash_session_model = user_env['cash.session']

            counters = bill_counter_model.search([], order='bill_counter')

            result = []
            for counter in counters:
                # Get all open sessions at this counter (one per user)
                open_sessions = cash_session_model.search([
                    ('counter_id', '=', counter.id),
                    ('status', '=', 'open')
                ])

                open_sessions_info = [
                    {
                        'session_id': session.id,
                        'external_user_id': session.external_user_id,
                        'external_user_name': session.external_user_name,
                    }
                    for session in open_sessions
                ]

                result.append({
                    'id': counter.id,
                    'name': counter.bill_counter,
                    'x_care_id': counter.x_care_id or '',
                    'is_main_cash': counter.is_main_cash,
                    'open_sessions': open_sessions_info,
                    'open_session_count': len(open_sessions),
                })

            return result

        except Exception as e:
            raise ValueError(str(e))

    @classmethod
    def _session_to_dict(cls, session):
        """Convert session record to dictionary."""
        return {
            'id': session.id,
            'external_user_id': session.external_user_id,
            'external_user_name': session.external_user_name,
            'counter_id': session.counter_id.id,
            'counter_x_care_id': session.counter_id.x_care_id,
            'counter_name': session.counter_id.bill_counter,
            'status': session.status,
            'opening_balance': session.opening_balance,
            'expected_amount': session.expected_amount,
            'pending_outgoing_amount': session.pending_outgoing_amount,
            'available_balance': session.available_balance,
            'opened_at': session.opened_at.isoformat() if session.opened_at else None,
            'closed_at': session.closed_at.isoformat() if session.closed_at else None,
            'closing_expected': session.closing_expected,
            'closing_declared': session.closing_declared,
            'closing_difference': session.closing_difference,
            'difference_status': session.difference_status,
            'payment_count': session.payment_count,
            'pending_outgoing_count': session.pending_outgoing_count,
            'pending_incoming_count': session.pending_incoming_count,
        }

    @classmethod
    def _transfer_to_dict(cls, transfer):
        """Convert transfer record to dictionary."""
        return {
            'id': transfer.id,
            'from_session_id': transfer.from_session_id.id,
            'from_user_name': transfer.from_user_name or None,
            'from_counter_name': transfer.from_counter_name or None,
            'to_session_id': transfer.to_session_id.id,
            'to_user_name': transfer.to_user_name or None,
            'to_counter_name': transfer.to_counter_name or None,
            'amount': transfer.amount,
            'denominations': transfer.denominations or None,
            'status': transfer.status,
            'created_by_name': transfer.created_by_name or None,
            'created_at': transfer.created_at.isoformat() if transfer.created_at else None,
            'resolved_by_name': transfer.resolved_by_name or None,
            'resolved_at': transfer.resolved_at.isoformat() if transfer.resolved_at else None,
            'reject_reason': transfer.reject_reason or None,
            'journal_entry_id': transfer.journal_entry_id.id if transfer.journal_entry_id else None,
        }
