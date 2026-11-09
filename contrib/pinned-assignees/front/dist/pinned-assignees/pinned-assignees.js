/*
 * Pinned assignees: show the pinned (group) accounts right after the current
 * user in the assignee dropdowns, so they are always within the first five.
 *
 * The back-end marks these accounts with `pinned_order` on the project
 * members (see PINNED_ASSIGNEE_USERNAMES). This plugin decorates
 * tgUserListService.searchUsers(), which feeds the "assigned to" dropdowns
 * of issues, tasks and user stories, and re-sorts its result:
 *
 *   1. the current user,
 *   2. the pinned accounts, by `pinned_order`,
 *   3. everyone else, in Taiga's own order.
 */
(function () {
    "use strict";

    var CURRENT_USER_RANK = -1;
    var UNPINNED_RANK = Number.MAX_SAFE_INTEGER;

    function getRank(user, currentUserId) {
        if (currentUserId !== null && user.id === currentUserId) {
            return CURRENT_USER_RANK;
        }
        if (typeof user.pinned_order === "number") {
            return user.pinned_order;
        }
        return UNPINNED_RANK;
    }

    function sortUsers(users, currentUserId) {
        // _.sortBy is stable, so users with the same rank keep their order.
        return _.sortBy(users, function (user) {
            return getRank(user, currentUserId);
        });
    }

    angular.module("maykinPinnedAssignees", ["taigaCommon"])
        .config(["$provide", function ($provide) {
            $provide.decorator("tgUserListService", ["$delegate", function ($delegate) {
                var searchUsers = $delegate.searchUsers;

                $delegate.searchUsers = function (text, excludedUser) {
                    var users = searchUsers.call($delegate, text, excludedUser);
                    var currentUser = $delegate.currentUserService.getUser();
                    var currentUserId = currentUser ? currentUser.get("id") : null;
                    return sortUsers(users, currentUserId);
                };

                return $delegate;
            }]);
        }]);
})();
