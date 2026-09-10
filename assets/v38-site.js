(function () {
  'use strict';

  const TAB_SELECTOR =
    'a.tabx[href^="#"]';

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

  function targetOf(tab) {
    const href =
      tab.getAttribute('href') || '';

    if (
      href.length > 1 &&
      href.charAt(0) === '#'
    ) {
      const id = href.slice(1);
      if (SECTION_IDS.includes(id)) {
        return id;
      }
    }

    return null;
  }

  function suppressMockContent() {
    SECTION_IDS.forEach(
      (id) => {
        const section =
          document.getElementById(id);

        if (!section) {
          return;
        }

        Array.from(section.children)
          .forEach(
            (child) => {
              if (
                !child.classList.contains(
                  'v38-production-state'
                )
              ) {
                child.hidden = true;
                child.setAttribute(
                  'aria-hidden',
                  'true'
                );
              }
            }
          );
      }
    );
  }

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
      SECTION_IDS.includes(targetId)
        ? targetId
        : 't-market';

    tabs.forEach(
      (tab) => {
        const active =
          targetOf(tab) === valid;

        tab.classList.toggle(
          'active',
          active
        );

        tab.setAttribute(
          'aria-selected',
          active ? 'true' : 'false'
        );
      }
    );

    SECTION_IDS.forEach(
      (id) => {
        const section =
          document.getElementById(id);

        if (!section) {
          return;
        }

        const active =
          id === valid;

        section.classList.toggle(
          'active',
          active
        );

        section.hidden = !active;
      }
    );

    if (
      updateHash &&
      window.location.hash !==
        '#' + valid
    ) {
      history.replaceState(
        null,
        '',
        '#' + valid
      );
    }
  }

  function sectionDetail(section) {
    if (
      !section ||
      !Array.isArray(section.components)
    ) {
      return (
        'Authoritative inputs are unavailable. ' +
        'Mock values remain shielded.'
      );
    }

    const parts =
      section.components.map(
        (row) => {
          const status =
            typeof row.status === 'string'
              ? row.status
              : 'DATA_REQUIRED';

          const reason =
            typeof row.reason === 'string'
              ? row.reason
              : 'UNKNOWN';

          return (
            row.name +
            ': ' +
            status +
            ' (' +
            reason +
            ')'
          );
        }
      );

    return parts.join(' • ');
  }

  function renderPayload(payload) {
    const sections =
      payload &&
      payload.sections &&
      typeof payload.sections === 'object'
        ? payload.sections
        : {};

    SECTION_IDS.forEach(
      (id) => {
        const node =
          document.querySelector(
            '.v38-production-state' +
            '[data-v38-section="' +
            id +
            '"]'
          );

        if (!node) {
          return;
        }

        const section =
          sections[id] || null;

        const status =
          section &&
          typeof section.status === 'string'
            ? section.status
            : 'DATA_REQUIRED';

        const title =
          node.querySelector('b');

        const body =
          node.querySelector('span');

        if (title) {
          title.textContent = status;
        }

        if (body) {
          body.textContent =
            sectionDetail(section);
        }

        node.dataset.v38Status = status;
      }
    );
  }

  function setAllUnavailable(detail) {
    document
      .querySelectorAll(
        '.v38-production-state'
      )
      .forEach(
        (node) => {
          const title =
            node.querySelector('b');
          const body =
            node.querySelector('span');

          if (title) {
            title.textContent =
              'DATA_REQUIRED';
          }

          if (body) {
            body.textContent = detail;
          }

          node.dataset.v38Status =
            'DATA_REQUIRED';
        }
      );
  }

  async function loadPayload() {
    const runtime =
      window.V38Runtime;

    if (
      !runtime ||
      typeof runtime.loadJson !==
        'function'
    ) {
      setAllUnavailable(
        'Runtime unavailable. ' +
        'Mock values remain shielded.'
      );
      return;
    }

    try {
      const payload =
        await runtime.loadJson(
          'data/ui_payload.json'
        );

      renderPayload(payload);
    } catch (_) {
      setAllUnavailable(
        'Authoritative ui_payload.json ' +
        'is unavailable. ' +
        'Mock values remain shielded.'
      );
    }
  }

  document.addEventListener(
    'DOMContentLoaded',
    () => {
      suppressMockContent();

      document
        .querySelectorAll(
          TAB_SELECTOR
        )
        .forEach(
          (tab) => {
            tab.addEventListener(
              'click',
              (event) => {
                const target =
                  targetOf(tab);

                if (!target) {
                  return;
                }

                event.preventDefault();

                activate(
                  target,
                  true
                );
              }
            );
          }
        );

      const requested =
        window.location.hash
          ? window.location.hash.slice(1)
          : '';

      const initiallyActive =
        Array.from(
          document.querySelectorAll(
            TAB_SELECTOR
          )
        ).find(
          (tab) =>
            tab.classList.contains(
              'active'
            )
        );

      activate(
        SECTION_IDS.includes(requested)
          ? requested
          : (
              initiallyActive
                ? targetOf(
                    initiallyActive
                  )
                : 't-market'
            ),
        false
      );

      loadPayload();
    }
  );
})();
