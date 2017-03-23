[]( -*-mode: org; coding: utf-8;-*- )

# FAQ

## No user manual ?

It's being rewritten and translated to english.

## No web GUI ?

Yep, no web. Although going full HTML would make our life easier
as far as deployment is concerned, we think that for enterprise
context Qt is the right choice : it is super mature and super
stable.

Now, that was the reasoning when we started Koï. We might reconsider
this if we figure out a good combinations of various UI components.
The biggest dark spot right now is a good and powerful table editor
as Koï ergonomics are quite optimized there.

Moreover, we intend to change the current "direct access to DB"
paradigm to a REST/RPC JSON API. That will make the server installable
on the Cloud.


## No accounting ?

Yep, that's right. Our customers don't care.


## No git history ?

Koï was initially developped as GPL'ed software for a few customers
and it remained in their companies. Now that it's mature enough, we publish
it. However, as time when by, some intelectual property from these
customers was added into our git repository. Since that can't be removed
from the git history, we had to start a new repository, cleaned
from any IP infringement.
