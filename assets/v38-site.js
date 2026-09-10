(function () {
  'use strict';

  const TAB_SELECTOR =
    'a.tabx[data-target]';

  const SECTION_IDS = [
    't-market',
    't-alloc',
    't-port',
    't-rotation',
    't-rs',
    't-weekly',
    't-options',
    't-post1',
    't-rules'
  ];

  function activate(
    targetId,
    updateHash
  ) {
    const tabs = Array.from(
      document.querySelectorAll(
        TAB_SELECTOR
      )
    );

    const valid =
      SECTION_IDS.includes(
        targetId
      )
        ? targetId
        : 't-market';

    tabs.forEach(
      (tab) => {
        const active =
          tab.dataset.target
          === valid;

        tab.classList.toggle(
          'active',
          active
        );

        tab.setAttribute(
          'aria-selected',
          active
            ? 'true'
            : 'false'
        );
      }
    );

    SECTION_IDS.forEach(
      (id) => {
        const section =
          document.getElementById(
            id
          );

        if (!section) {
          return;
        }

        const active =
          id === valid;

        section.classList.toggle(
          'active',
          active
        );

        section.hidden =
          !active;
      }
    );

    if (
      updateHash
      && window.location.hash
      !== '#' + valid
    ) {
      history.replaceState(
        null,
        '',
        '#' + valid
      );
    }
  }

  function setSafeState(
    status,
    detail
  ) {
    document
      .querySelectorAll(
        '.v38-production-state'
      )
      .forEach(
        (node) => {
          const title =
            node.querySelector(
              'b'
            );

          const body =
            node.querySelector(
              'span'
            );

          if (title) {
            title.textContent =
              status;
          }

          if (body) {
            body.textContent =
              detail;
          }
        }
      );
  }

  async function inspectPayload() {
    const runtime =
      window.V38Runtime;

    if (
      !runtime
      || typeof runtime.loadJson
      !== 'function'
    ) {
      setSafeState(
        'DATA_REQUIRED',
        (
          'Runtime unavailable. '
          + 'Mock values remain '
          + 'shielded.'
        )
      );

      return;
    }

    try {
      const payload =
        await runtime.loadJson(
          'data/ui_payload.json'
        );

      const status =
        payload
        && typeof payload.status
        === 'string'
          ? payload.status
          : 'DATA_REQUIRED';

      setSafeState(
        status,
        status === 'READY'
          ? (
              'Authoritative payload '
              + 'detected. Card binding '
              + 'is intentionally '
              + 'pending the next '
              + 'verified stage.'
            )
          : (
              'Authoritative payload '
              + 'is not ready. '
              + 'Mock values remain '
              + 'shielded.'
            )
      );

    } catch (_) {
      setSafeState(
        'DATA_REQUIRED',
        (
          'Authoritative '
          + 'ui_payload.json is '
          + 'unavailable. '
          + 'Mock values remain '
          + 'shielded.'
        )
      );
    }
  }

  document.addEventListener(
    'DOMContentLoaded',
    () => {
      document
        .querySelectorAll(
          TAB_SELECTOR
        )
        .forEach(
          (tab) => {
            tab.addEventListener(
              'click',
              (event) => {
                event.preventDefault();

                activate(
                  tab.dataset.target,
                  true
                );
              }
            );
          }
        );

      const requested =
        window.location.hash
          ? window.location.hash.slice(
              1
            )
          : '';

      const initiallyActive =
        document.querySelector(
          TAB_SELECTOR
          + '.active'
        );

      activate(
        SECTION_IDS.includes(
          requested
        )
          ? requested
          : (
              initiallyActive
                ? initiallyActive
                    .dataset
                    .target
                : 't-market'
            ),
        false
      );

      inspectPayload();
    }
  );
})();
