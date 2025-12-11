import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.DenominationView = publicWidget.Widget.extend({
    selector: '.cash_denomination_register_template',
    events: {
        'click .view-denomination-btn': '_toggleDenominationBox',
        'click .close-denomination-btn': '_closeDenominationBox',
    },

    _toggleDenominationBox: function (ev) {
        ev.stopPropagation();
        const $button = $(ev.currentTarget);
        const hasLines = $button.data("has-lines");
        const $box = $button.siblings('.denomination-box');

        const $msg = $box.find('.no-lines-message');
        const $table = $box.find('.denomination-table');

        // -------- CLOSE ANY OPEN BOX BEFORE OPENING NEW ONE ----------
        $(".denomination-box").not($box).slideUp();

        if (!hasLines) {
            $table.hide();
            $msg.show();
        } else {
            $msg.hide();
            $table.show();
        }

        $box.slideToggle();

        $(document).off('click.denominationOutside').on('click.denominationOutside', function (e) {
            if (
                !$box.is(e.target) &&
                $box.has(e.target).length === 0 &&
                !$button.is(e.target)
            ) {
                $box.slideUp();
                $(document).off('click.denominationOutside');
            }
        });
    },

    _closeDenominationBox: function (ev) {
        ev.stopPropagation();
        const $box = $(ev.currentTarget).closest('.denomination-box');
        $box.slideUp();
        $(document).off('click.denominationOutside');
    },
});
