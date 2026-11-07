# Pinned assignees

Shows a fixed set of (group) accounts, e.g. support, devops and sales, right
after the current user in the "assigned to" dropdown, so they are always among
the first five users when creating an issue or task.

Resulting order in the dropdown:

1. the current user,
2. the pinned accounts, in the configured order,
3. everyone else, in Taiga's default order.

Typing in the dropdown's search box still filters the whole list; the matches
keep this order.

## How it works

- **Back-end** (this repository): the usernames are configured with the
  `PINNED_ASSIGNEE_USERNAMES` environment variable. The project API exposes
  each member's position in that list as `pinned_order` (`null` when not
  pinned).
- **Front-end**: `front/dist/pinned-assignees` is a Taiga contrib plugin for
  the stock `taiga-front` / `taiga-front-dist`. It decorates
  `tgUserListService.searchUsers()` and sorts on `pinned_order`. No fork or
  rebuild of the front-end is needed.

The plugin affects the dropdowns that use `searchUsers()`: the "assigned to"
field in the new/edit issue and task forms, and the user story assignees
dropdown. The "Add assigned" lightbox on the issue detail page lists all
members alphabetically and is not changed.

## Deployment

### Back-end

```
PINNED_ASSIGNEE_USERNAMES=<support-user>,<devops-user>,<sales-user>
```

Usernames are matched exactly; the accounts must be members of a project to
show up in its dropdown.

### Front-end (taigaio/taiga-front Docker image)

1. Make the plugin available in the container at
   `/usr/share/nginx/html/plugins/pinned-assignees/`, e.g. with a volume:

   ```
   -v ./contrib/pinned-assignees/front/dist/pinned-assignees:/usr/share/nginx/html/plugins/pinned-assignees:ro
   ```

2. Add the plugin to `contribPlugins` in the front-end `conf.json`:

   ```json
   "contribPlugins": ["plugins/pinned-assignees/pinned-assignees.json"]
   ```

   The image generates `conf.json` from environment variables only when the
   file does not exist yet, and has no variable for custom plugins. So mount
   your own `conf.json` at `/usr/share/nginx/html/conf.json`, based on the
   generated one.

Tested with the `taigaio/taiga-front:6.8.2` image.
