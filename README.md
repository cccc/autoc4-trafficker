# Trafficker
A program that collects train, tram and Bus departures in Cologne Ehrenfeld and converts the departure list to a JSON format that can be processed by the JSON screen.

This uses pyhafas to get the information via a KVB Hafas client. There still is a bunch of stuff to do here, but so far, this gets a significantly improved experience of what gets displayed on the departures table at any given moment.

This idea was initially Kadses, the first implementation (and pretty much all the logic and research) were done by fwam, emma added formal improvements and improvements in the code, and eventually restructured it to make the API calls asynchronously to improve performance.
